import re
import logging
import asyncio
from typing import Optional, Callable
from backend.core.schemas import Job, Resume, MatchResult
from backend.utils.ollama_client import OllamaClient, OllamaJSONParseError
from backend.utils.prompt_templates import (
    scorer_system_prompt,
    scorer_user_prompt,
)

logger = logging.getLogger(__name__)


# ── Exceptions ─────────────────────────────────────────────────────────────────

class ScorerError(Exception):
    """Raised when scoring fails critically."""


# ── Scorer Agent ───────────────────────────────────────────────────────────────

class ScorerAgent:
    """
    Agent 2 of the pipeline.
    Validates and normalizes MatchResults produced by the MatcherAgent.

    Responsibilities:
    - Detect and correct inflated/deflated scores from matcher
    - Normalize score_breakdown consistency
    - Apply experience-based score penalty/bonus
    - Apply title alignment bonus
    - Flag high-potential and low-effort opportunities
    - Graceful fallback to statistical normalization on LLM failure
    """

    STRONG_MATCH_THRESHOLD  = 7.5
    WEAK_MATCH_THRESHOLD    = 4.0
    MAX_CONCURRENCY         = 1
    EXP_PENALTY_PER_YEAR    = 0.3
    MAX_EXP_PENALTY         = 2.0

    def __init__(self, ollama_client: Optional[OllamaClient] = None):
        self._ollama = ollama_client or OllamaClient()
        self._semaphore = asyncio.Semaphore(self.MAX_CONCURRENCY)

    # ── Public API ─────────────────────────────────────────────────────────────

    async def score_one(
        self,
        resume: Resume,
        job: Job,
        match: MatchResult,
    ) -> MatchResult:
        """
        Validate and finalize a single MatchResult.
        Applies LLM review + statistical adjustments.
        Always returns a MatchResult — never raises.
        """
        adjusted = self._statistical_adjust(resume, job, match)

        if self._needs_llm_review(adjusted):
            async with self._semaphore:
                llm_result = await self._llm_score(resume, job, adjusted)
                if llm_result:
                    adjusted = llm_result

        final = self._post_process(resume, job, adjusted)

        logger.info(
            f"[scorer] '{job.title}' at {job.company} → "
            f"{match.fit_score:.1f} → {final.fit_score:.1f} "
            f"({'↑' if final.fit_score > match.fit_score else '↓' if final.fit_score < match.fit_score else '='}"
            f"{abs(final.fit_score - match.fit_score):.1f})"
        )
        return final

    async def score_many(
        self,
        resume: Resume,
        jobs: list[Job],
        matches: list[MatchResult],
        on_progress: Optional[Callable] = None,
    ) -> list[MatchResult]:
        """
        Score a list of MatchResults concurrently.
        jobs and matches must be parallel lists (same index = same job).
        Returns scored results sorted by fit_score descending.
        """
        if not matches:
            return []

        job_map: dict[str, Job] = {job.id: job for job in jobs}

        logger.info(f"[scorer] Scoring {len(matches)} match results")

        results: list[MatchResult] = []
        total = len(matches)
        completed = 0
        lock = asyncio.Lock()

        async def process(match: MatchResult):
            nonlocal completed
            job = job_map.get(match.job_id)
            if not job:
                logger.warning(f"[scorer] No job found for match {match.job_id} — skipping")
                async with lock:
                    completed += 1
                return

            result = await self.score_one(resume, job, match)

            async with lock:
                completed += 1
                results.append(result)
                if on_progress:
                    try:
                        await on_progress(completed, total)
                    except Exception:
                        pass

        await asyncio.gather(*[process(m) for m in matches])

        results.sort(key=lambda r: r.fit_score, reverse=True)

        avg = sum(r.fit_score for r in results) / len(results) if results else 0.0
        logger.info(
            f"[scorer] Done. Avg score: {avg:.1f} | "
            f"Strong matches (≥{self.STRONG_MATCH_THRESHOLD}): "
            f"{sum(1 for r in results if r.fit_score >= self.STRONG_MATCH_THRESHOLD)}"
        )
        return results

    # ── Statistical Adjustment ─────────────────────────────────────────────────

    def _statistical_adjust(
        self,
        resume: Resume,
        job: Job,
        match: MatchResult,
    ) -> MatchResult:
        """
        Apply rule-based score corrections before LLM review.

        Adjustments:
        1. Experience gap penalty
        2. Title alignment bonus
        3. Score breakdown consistency check
        """
        score = match.fit_score
        breakdown = dict(match.score_breakdown)

        # ── 1. Experience gap penalty ──────────────────────────────────────────
        required_exp = self._extract_required_experience(job.description)
        candidate_exp = resume.experience_years or 0.0

        if required_exp and candidate_exp < required_exp:
            gap = required_exp - candidate_exp
            penalty = min(gap * self.EXP_PENALTY_PER_YEAR, self.MAX_EXP_PENALTY)
            score = max(0.0, score - penalty)
            breakdown["experience"] = max(0.0, breakdown.get("experience", score) - penalty)
            logger.debug(
                f"[scorer] Exp penalty: -{penalty:.1f} "
                f"(required {required_exp}yr, candidate {candidate_exp}yr)"
            )

        # ── 2. Title alignment bonus ───────────────────────────────────────────
        if resume.current_title and job.title:
            title_bonus = self._title_alignment_bonus(resume.current_title, job.title)
            if title_bonus > 0:
                score = min(10.0, score + title_bonus)
                breakdown["role_alignment"] = min(
                    10.0, breakdown.get("role_alignment", score) + title_bonus
                )
                logger.debug(f"[scorer] Title bonus: +{title_bonus:.1f}")

        # ── 3. Breakdown consistency ───────────────────────────────────────────
        if breakdown:
            breakdown_avg = sum(breakdown.values()) / len(breakdown)
            deviation = abs(breakdown_avg - score)
            if deviation > 2.0:
                factor = score / breakdown_avg if breakdown_avg > 0 else 1.0
                breakdown = {k: min(10.0, max(0.0, v * factor)) for k, v in breakdown.items()}

        score = round(max(0.0, min(10.0, score)), 1)

        return MatchResult(
            job_id=match.job_id,
            fit_score=score,
            score_breakdown=breakdown,
            matched_skills=match.matched_skills,
            missing_skills=match.missing_skills,
            reasoning=match.reasoning,
        )

    # ── LLM Review ─────────────────────────────────────────────────────────────

    def _needs_llm_review(self, match: MatchResult) -> bool:
        """Only send borderline scores to LLM review. Saves inference time."""
        return 3.5 <= match.fit_score <= 8.0

    async def _llm_score(
        self,
        resume: Resume,
        job: Job,
        match: MatchResult,
    ) -> Optional[MatchResult]:
        """
        Ask LLM to validate and potentially adjust the match score.
        Returns updated MatchResult or None on failure.
        """
        try:
            raw = await self._ollama.chat_json(
                prompt=scorer_user_prompt(resume, job, match.model_dump()),
                system=scorer_system_prompt(),
                temperature=0.1,
            )
            return self._parse_score_result(raw, match)

        except OllamaJSONParseError as e:
            logger.warning(f"[scorer] JSON parse failed for job {match.job_id}: {e}")
            return None

        except Exception as e:
            logger.error(f"[scorer] LLM scoring failed for job {match.job_id}: {e}")
            return None

    def _parse_score_result(self, raw: dict, original: MatchResult) -> MatchResult:
        """
        Parse LLM scoring response.
        Protects against wild score swings — max ±2.0 change allowed.
        """
        def clamp(val, lo=0.0, hi=10.0) -> float:
            try:
                return max(lo, min(hi, float(val)))
            except (TypeError, ValueError):
                return original.fit_score

        raw_score = clamp(raw.get("fit_score", original.fit_score))

        max_delta = 2.0
        delta = raw_score - original.fit_score
        if abs(delta) > max_delta:
            raw_score = original.fit_score + (max_delta * (1 if delta > 0 else -1))
            logger.debug(
                f"[scorer] LLM score delta clamped: "
                f"{original.fit_score:.1f} → {raw_score:.1f}"
            )

        raw_breakdown = raw.get("score_breakdown", {})
        score_breakdown = {
            "skills":         clamp(raw_breakdown.get("skills",         original.score_breakdown.get("skills", raw_score))),
            "experience":     clamp(raw_breakdown.get("experience",     original.score_breakdown.get("experience", raw_score))),
            "role_alignment": clamp(raw_breakdown.get("role_alignment", original.score_breakdown.get("role_alignment", raw_score))),
            "culture_fit":    clamp(raw_breakdown.get("culture_fit",    original.score_breakdown.get("culture_fit", raw_score))),
        }

        matched_skills = [
            str(s).strip() for s in raw.get("matched_skills", original.matched_skills)
            if s is not None and str(s).strip()
        ]
        missing_skills = [
            str(s).strip() for s in raw.get("missing_skills", original.missing_skills)
            if s is not None and str(s).strip()
        ]
        reasoning = str(raw.get("reasoning", original.reasoning))[:500]

        return MatchResult(
            job_id=original.job_id,
            fit_score=round(raw_score, 1),
            score_breakdown=score_breakdown,
            matched_skills=matched_skills or original.matched_skills,
            missing_skills=missing_skills or original.missing_skills,
            reasoning=reasoning,
        )

    # ── Post Processing ────────────────────────────────────────────────────────

    def _post_process(
        self,
        resume: Resume,
        job: Job,
        match: MatchResult,
    ) -> MatchResult:
        """
        Final pass:
        - Hard clamp fit_score to [0, 10]
        - Enrich reasoning with opportunity flag
        - Normalize breakdown values
        """
        score = round(max(0.0, min(10.0, match.fit_score)), 1)

        reasoning = match.reasoning
        if score >= self.STRONG_MATCH_THRESHOLD:
            flag = " [STRONG MATCH — apply soon]"
        elif score < self.WEAK_MATCH_THRESHOLD:
            flag = " [WEAK MATCH — consider skipping]"
        else:
            flag = ""

        if flag and flag not in reasoning:
            reasoning = (reasoning + flag)[:500]

        breakdown = {
            k: round(max(0.0, min(10.0, v)), 1)
            for k, v in match.score_breakdown.items()
        }

        return MatchResult(
            job_id=match.job_id,
            fit_score=score,
            score_breakdown=breakdown,
            matched_skills=match.matched_skills,
            missing_skills=match.missing_skills,
            reasoning=reasoning,
        )

    # ── Helpers ────────────────────────────────────────────────────────────────

    def _extract_required_experience(self, description: str) -> Optional[float]:
        """Extract required years of experience from job description."""
        patterns = [
            r"(\d+)\+?\s*years?\s+of\s+experience",
            r"(\d+)\+?\s*years?\s+experience",
            r"minimum\s+(\d+)\s+years?",
            r"at\s+least\s+(\d+)\s+years?",
        ]
        for pattern in patterns:
            match = re.search(pattern, description.lower())
            if match:
                try:
                    return float(match.group(1))
                except ValueError:
                    continue
        return None

    def _title_alignment_bonus(self, candidate_title: str, job_title: str) -> float:
        """
        Return a small bonus (0.0–0.5) if candidate title aligns with job title.
        Uses keyword overlap — no LLM needed.
        """
        candidate_words = set(candidate_title.lower().split())
        job_words = set(job_title.lower().split())

        stop = {"the", "a", "an", "and", "or", "of", "in", "at", "for", "to"}
        candidate_words -= stop
        job_words -= stop

        if not candidate_words or not job_words:
            return 0.0

        overlap = len(candidate_words & job_words)
        score = overlap / max(len(candidate_words), len(job_words))

        if score >= 0.6:
            return 0.5
        elif score >= 0.3:
            return 0.25
        return 0.0