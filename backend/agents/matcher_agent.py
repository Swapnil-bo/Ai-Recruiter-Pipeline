import logging
import asyncio
from typing import Optional
from backend.core.schemas import Job, Resume, MatchResult
from backend.utils.ollama_client import OllamaClient, OllamaJSONParseError
from backend.utils.prompt_templates import (
    matcher_system_prompt,
    matcher_user_prompt,
)

logger = logging.getLogger(__name__)


# ── Exceptions ─────────────────────────────────────────────────────────────────

class MatcherError(Exception):
    """Raised when matching fails for a job."""


# ── Matcher Agent ──────────────────────────────────────────────────────────────

class MatcherAgent:
    """
    Agent 1 of the pipeline.
    Semantically matches a resume against job listings using Ollama.

    Responsibilities:
    - Rule-based pre-filter (skip obviously irrelevant jobs)
    - LLM-based deep semantic matching
    - Structured MatchResult output with score breakdown
    - Concurrent batch processing with rate limiting
    - Graceful fallback on LLM failure
    """

    # Jobs below this rule-based score skip LLM entirely — saves inference time
    RULE_FILTER_THRESHOLD = 0.15

    # Max concurrent LLM calls — respect 6GB VRAM limit
    MAX_CONCURRENCY = 1

    def __init__(self, ollama_client: Optional[OllamaClient] = None):
        self._ollama = ollama_client or OllamaClient()
        self._semaphore = asyncio.Semaphore(self.MAX_CONCURRENCY)

    # ── Public API ─────────────────────────────────────────────────────────────

    async def match_one(self, resume: Resume, job: Job) -> Optional[MatchResult]:
        """
        Match a single job against the resume.
        Returns None if job is filtered out or matching fails.
        """
        # Fast rule-based pre-filter
        rule_score = self._rule_based_score(resume, job)
        if rule_score < self.RULE_FILTER_THRESHOLD:
            logger.debug(
                f"[matcher] Filtered out '{job.title}' at {job.company} "
                f"(rule score: {rule_score:.2f})"
            )
            return None

        # LLM deep match
        async with self._semaphore:
            return await self._llm_match(resume, job, rule_score)

    async def match_many(
        self,
        resume: Resume,
        jobs: list[Job],
        on_progress: Optional[callable] = None,
    ) -> list[MatchResult]:
        """
        Match resume against a list of jobs concurrently.
        Respects MAX_CONCURRENCY to avoid overloading local Ollama.
        Calls on_progress(current, total) after each job completes.

        Returns only successful MatchResults, sorted by fit_score desc.
        """
        if not jobs:
            return []

        logger.info(f"[matcher] Matching resume against {len(jobs)} jobs")

        results: list[MatchResult] = []
        total = len(jobs)
        completed = 0
        lock = asyncio.Lock()

        async def process(job: Job):
            nonlocal completed
            result = await self.match_one(resume, job)
            async with lock:
                completed += 1
                if result:
                    results.append(result)
                if on_progress:
                    try:
                        await on_progress(completed, total)
                    except Exception:
                        pass
            logger.info(
                f"[matcher] {completed}/{total} — "
                f"'{job.title}' → "
                f"{'score: ' + str(round(result.fit_score, 1)) if result else 'filtered'}"
            )

        await asyncio.gather(*[process(job) for job in jobs])

        # Sort by fit_score descending
        results.sort(key=lambda r: r.fit_score, reverse=True)
        logger.info(
            f"[matcher] Done. {len(results)}/{total} jobs matched. "
            f"Top score: {results[0].fit_score if results else 'N/A'}"
        )
        return results

    # ── Rule-Based Pre-Filter ──────────────────────────────────────────────────

    def _rule_based_score(self, resume: Resume, job: Job) -> float:
        """
        Fast keyword overlap score between resume skills and job content.
        Returns a float 0.0–1.0.
        Used to skip obviously irrelevant jobs before LLM inference.
        """
        if not resume.skills:
            return 1.0                   # no skills on resume → don't filter

        resume_skills = {s.lower() for s in resume.skills}
        job_text = " ".join([
            job.title,
            job.description,
            " ".join(job.tags),
        ]).lower()

        matched = sum(1 for skill in resume_skills if skill in job_text)
        score = matched / len(resume_skills)
        return score

    # ── LLM Matching ───────────────────────────────────────────────────────────

    async def _llm_match(
        self,
        resume: Resume,
        job: Job,
        rule_score: float,
    ) -> Optional[MatchResult]:
        """
        Deep semantic match using Ollama.
        Parses structured JSON response into MatchResult.
        Falls back to rule-based result on LLM failure.
        """
        try:
            raw = await self._ollama.chat_json(
                prompt=matcher_user_prompt(resume, job),
                system=matcher_system_prompt(),
                temperature=0.2,
            )
            return self._parse_match_result(raw, job.id)

        except OllamaJSONParseError as e:
            logger.warning(f"[matcher] JSON parse failed for '{job.title}': {e}")
            return self._fallback_result(resume, job, rule_score)

        except Exception as e:
            logger.error(f"[matcher] LLM match failed for '{job.title}': {e}")
            return self._fallback_result(resume, job, rule_score)

    def _parse_match_result(self, raw: dict, job_id: str) -> MatchResult:
        """
        Parse and validate raw LLM JSON output into a MatchResult.
        Clamps scores to valid range. Fills missing fields with defaults.
        """
        def clamp(val, lo=0.0, hi=10.0) -> float:
            try:
                return max(lo, min(hi, float(val)))
            except (TypeError, ValueError):
                return 5.0

        fit_score = clamp(raw.get("fit_score", 5.0))

        raw_breakdown = raw.get("score_breakdown", {})
        score_breakdown = {
            "skills":        clamp(raw_breakdown.get("skills", fit_score)),
            "experience":    clamp(raw_breakdown.get("experience", fit_score)),
            "role_alignment": clamp(raw_breakdown.get("role_alignment", fit_score)),
            "culture_fit":   clamp(raw_breakdown.get("culture_fit", fit_score)),
        }

        matched_skills = [
            str(s) for s in raw.get("matched_skills", [])
            if s and isinstance(s, str)
        ]
        missing_skills = [
            str(s) for s in raw.get("missing_skills", [])
            if s and isinstance(s, str)
        ]
        reasoning = str(raw.get("reasoning", "No reasoning provided."))[:500]

        return MatchResult(
            job_id=job_id,
            fit_score=fit_score,
            score_breakdown=score_breakdown,
            matched_skills=matched_skills,
            missing_skills=missing_skills,
            reasoning=reasoning,
        )

    # ── Fallback ───────────────────────────────────────────────────────────────

    def _fallback_result(
        self,
        resume: Resume,
        job: Job,
        rule_score: float,
    ) -> MatchResult:
        """
        Rule-based fallback MatchResult when LLM fails.
        Converts rule_score (0–1) to fit_score (0–10).
        """
        fit_score = round(rule_score * 10, 1)

        resume_skills = {s.lower() for s in resume.skills}
        job_text = " ".join([job.title, job.description, " ".join(job.tags)]).lower()

        matched = [s for s in resume_skills if s in job_text]
        missing = [s for s in resume_skills if s not in job_text]

        return MatchResult(
            job_id=job.id,
            fit_score=fit_score,
            score_breakdown={
                "skills": fit_score,
                "experience": fit_score,
                "role_alignment": fit_score,
                "culture_fit": fit_score,
            },
            matched_skills=matched[:20],
            missing_skills=missing[:20],
            reasoning=(
                f"LLM matching unavailable. Rule-based score: {fit_score}/10 "
                f"based on {len(matched)} skill matches."
            ),
        )