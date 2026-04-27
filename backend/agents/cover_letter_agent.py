import re
import logging
import asyncio
from typing import Optional, Callable
from backend.core.schemas import Job, Resume, CoverLetter, MatchResult
from backend.utils.ollama_client import OllamaClient, OllamaTimeoutError
from backend.utils.prompt_templates import (
    cover_letter_system_prompt,
    cover_letter_user_prompt,
)

logger = logging.getLogger(__name__)


# ── Exceptions ─────────────────────────────────────────────────────────────────

class CoverLetterError(Exception):
    """Raised when cover letter generation fails critically."""

class CoverLetterTooShortError(CoverLetterError):
    """Raised when generated content is suspiciously short."""


# ── Cover Letter Agent ─────────────────────────────────────────────────────────

class CoverLetterAgent:
    """
    Agent 3 of the pipeline.
    Generates tailored cover letters for high-scoring job matches.

    Responsibilities:
    - Filter jobs below minimum fit score (no wasted inference)
    - Stream cover letter generation token by token
    - Post-process: clean, validate length, remove AI artifacts
    - Detect and retry on low-quality output
    - Batch generation with progress tracking
    """

    # Only generate cover letters for jobs above this score
    MIN_FIT_SCORE_FOR_GENERATION = 5.0

    # Quality thresholds
    MIN_WORD_COUNT   = 150
    MAX_WORD_COUNT   = 500
    MAX_CONCURRENCY  = 1

    # Phrases that indicate the LLM ignored instructions
    BANNED_PHRASES = [
        "i am writing to express my interest",
        "i am writing to apply",
        "to whom it may concern",
        "dear hiring manager,",
        "i am excited to apply",
        "i would like to apply",
        "please find attached",
        "as per your job posting",
        "i came across your job posting",
    ]

    def __init__(self, ollama_client: Optional[OllamaClient] = None):
        self._ollama = ollama_client or OllamaClient()
        self._semaphore = asyncio.Semaphore(self.MAX_CONCURRENCY)

    # ── Public API ─────────────────────────────────────────────────────────────

    async def generate_one(
        self,
        resume: Resume,
        job: Job,
        fit_score: float,
        stream_callback: Optional[Callable[[str], None]] = None,
        max_retries: int = 2,
    ) -> Optional[CoverLetter]:
        """
        Generate a cover letter for a single job.

        Args:
            resume: Parsed resume
            job: Target job listing
            fit_score: Fit score from scorer agent
            stream_callback: Optional async callback for streaming tokens to frontend
            max_retries: Retry attempts on quality failure

        Returns:
            CoverLetter or None if score too low / generation failed
        """
        if fit_score < self.MIN_FIT_SCORE_FOR_GENERATION:
            logger.info(
                f"[cover_letter] Skipping '{job.title}' — "
                f"fit score {fit_score:.1f} below threshold "
                f"{self.MIN_FIT_SCORE_FOR_GENERATION}"
            )
            return None

        logger.info(
            f"[cover_letter] Generating for '{job.title}' at {job.company} "
            f"(fit: {fit_score:.1f})"
        )

        async with self._semaphore:
            for attempt in range(max_retries + 1):
                try:
                    content = await self._generate_content(
                        resume=resume,
                        job=job,
                        fit_score=fit_score,
                        stream_callback=stream_callback,
                    )

                    # Quality validation
                    quality_issue = self._check_quality(content)
                    if quality_issue:
                        logger.warning(
                            f"[cover_letter] Quality issue (attempt {attempt + 1}): "
                            f"{quality_issue}"
                        )
                        if attempt < max_retries:
                            await asyncio.sleep(1)
                            continue
                        else:
                            logger.warning(
                                f"[cover_letter] Using best available output "
                                f"after {max_retries + 1} attempts"
                            )

                    # Post-process
                    clean_content = self._post_process(content)

                    logger.info(
                        f"[cover_letter] Generated for '{job.title}' — "
                        f"{len(clean_content.split())} words"
                    )

                    return CoverLetter(
                        job_id=job.id,
                        content=clean_content,
                    )

                except OllamaTimeoutError as e:
                    logger.error(f"[cover_letter] Timeout on attempt {attempt + 1}: {e}")
                    if attempt == max_retries:
                        return self._fallback_cover_letter(resume, job, fit_score)

                except Exception as e:
                    logger.error(
                        f"[cover_letter] Generation failed (attempt {attempt + 1}): {e}"
                    )
                    if attempt == max_retries:
                        return self._fallback_cover_letter(resume, job, fit_score)

                await asyncio.sleep(1)

        return None

    async def generate_many(
        self,
        resume: Resume,
        jobs: list[Job],
        matches: list[MatchResult],
        on_progress: Optional[Callable] = None,
    ) -> list[CoverLetter]:
        """
        Generate cover letters for all qualifying jobs.
        Only generates for jobs above MIN_FIT_SCORE_FOR_GENERATION.
        Returns list of CoverLetters sorted by job fit score descending.
        """
        if not jobs or not matches:
            return []

        # Build score lookup
        job_map: dict[str, Job] = {job.id: job for job in jobs}

        # Only process qualifying jobs, sorted best first
        qualifying = sorted(
            [m for m in matches if m.fit_score >= self.MIN_FIT_SCORE_FOR_GENERATION],
            key=lambda m: m.fit_score,
            reverse=True,
        )

        if not qualifying:
            logger.info("[cover_letter] No jobs met minimum fit score threshold")
            return []

        logger.info(
            f"[cover_letter] Generating {len(qualifying)} cover letters "
            f"(of {len(matches)} total matches)"
        )

        results: list[CoverLetter] = []
        total = len(qualifying)
        completed = 0
        lock = asyncio.Lock()

        async def process(match: MatchResult):
            nonlocal completed
            job = job_map.get(match.job_id)
            if not job:
                return

            cover_letter = await self.generate_one(
                resume=resume,
                job=job,
                fit_score=match.fit_score,
            )

            async with lock:
                completed += 1
                if cover_letter:
                    results.append(cover_letter)
                if on_progress:
                    try:
                        await on_progress(completed, total)
                    except Exception:
                        pass

            logger.info(
                f"[cover_letter] {completed}/{total} — "
                f"'{job.title}' → "
                f"{'generated' if cover_letter else 'failed'}"
            )

        await asyncio.gather(*[process(m) for m in qualifying])

        logger.info(
            f"[cover_letter] Done. "
            f"{len(results)}/{len(qualifying)} cover letters generated"
        )
        return results

    # ── Generation ─────────────────────────────────────────────────────────────

    async def _generate_content(
        self,
        resume: Resume,
        job: Job,
        fit_score: float,
        stream_callback: Optional[Callable[[str], None]] = None,
    ) -> str:
        """
        Generate cover letter content.
        Uses streaming if callback provided, otherwise standard chat.
        """
        prompt = cover_letter_user_prompt(resume, job, fit_score)
        system = cover_letter_system_prompt()

        if stream_callback:
            return await self._stream_with_callback(
                prompt=prompt,
                system=system,
                callback=stream_callback,
            )
        else:
            return await self._ollama.stream_to_string(
                prompt=prompt,
                system=system,
                temperature=0.75,        # slightly creative for cover letters
            )

    async def _stream_with_callback(
        self,
        prompt: str,
        system: str,
        callback: Callable[[str], None],
    ) -> str:
        """Stream tokens and fire callback for each, collect full content."""
        chunks: list[str] = []
        async for token in self._ollama.stream(
            prompt=prompt,
            system=system,
            temperature=0.75,
        ):
            chunks.append(token)
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(token)
                else:
                    callback(token)
            except Exception as e:
                logger.warning(f"[cover_letter] Stream callback error: {e}")
        return "".join(chunks)

    # ── Quality Control ────────────────────────────────────────────────────────

    def _check_quality(self, content: str) -> Optional[str]:
        """
        Validate generated cover letter quality.
        Returns a string describing the issue, or None if quality is acceptable.
        """
        if not content or not content.strip():
            return "Empty content"

        word_count = len(content.split())

        if word_count < self.MIN_WORD_COUNT:
            return f"Too short: {word_count} words (min {self.MIN_WORD_COUNT})"

        if word_count > self.MAX_WORD_COUNT:
            # Not a hard failure — just warn, we'll trim in post-process
            logger.debug(f"[cover_letter] Content long: {word_count} words — will trim")

        # Check for banned cliché phrases
        content_lower = content.lower()
        for phrase in self.BANNED_PHRASES:
            if phrase in content_lower:
                return f"Contains banned phrase: '{phrase}'"

        # Check for placeholder artifacts
        if re.search(r"\[.*?\]", content):
            return "Contains unfilled placeholders like [Company Name]"

        # Check for JSON leakage (LLM sometimes outputs JSON instead of prose)
        if content.strip().startswith("{") or content.strip().startswith("["):
            return "Content looks like JSON, not prose"

        return None

    # ── Post Processing ────────────────────────────────────────────────────────

    def _post_process(self, content: str) -> str:
        """
        Clean and normalize generated cover letter content.

        Steps:
        1. Strip markdown artifacts (bold, italic, headers)
        2. Remove subject line / date if LLM included them
        3. Normalize paragraph spacing
        4. Trim to MAX_WORD_COUNT if needed
        5. Strip trailing whitespace
        """
        # Remove markdown formatting
        content = re.sub(r"\*\*(.+?)\*\*", r"\1", content)      # bold
        content = re.sub(r"\*(.+?)\*", r"\1", content)           # italic
        content = re.sub(r"^#{1,6}\s+", "", content, flags=re.MULTILINE)  # headers
        content = re.sub(r"^[-*]\s+", "", content, flags=re.MULTILINE)    # bullets

        # Remove subject line if present (e.g. "Subject: ..." or "Re: ...")
        content = re.sub(r"^(subject|re|date|from|to)\s*:.*\n?", "", content, flags=re.IGNORECASE | re.MULTILINE)

        # Remove common salutation/sign-off if LLM included them
        content = re.sub(r"^(dear\s+hiring\s+manager|dear\s+team|hello|hi\s+there)[,.]?\s*\n?", "", content, flags=re.IGNORECASE)
        content = re.sub(r"\n?(sincerely|best\s+regards|warm\s+regards|regards|thank\s+you)[,.]?\s*\n?.*$", "", content, flags=re.IGNORECASE)

        # Normalize paragraph spacing — max 2 consecutive newlines
        content = re.sub(r"\n{3,}", "\n\n", content)

        # Trim to word limit if needed
        words = content.split()
        if len(words) > self.MAX_WORD_COUNT:
            content = " ".join(words[:self.MAX_WORD_COUNT])
            # End on a complete sentence
            last_period = content.rfind(".")
            if last_period > len(content) * 0.7:
                content = content[:last_period + 1]

        return content.strip()

    # ── Fallback ───────────────────────────────────────────────────────────────

    def _fallback_cover_letter(
        self,
        resume: Resume,
        job: Job,
        fit_score: float,
    ) -> CoverLetter:
        """
        Template-based fallback when LLM generation fails entirely.
        Better than returning nothing — user can edit the template.
        """
        # Fallback intentionally uses simple template language.
        # Quality checks are skipped — user is expected to edit this output.
        skills_str = ", ".join(resume.skills[:5]) if resume.skills else "relevant skills"
        exp_str = f"{resume.experience_years} years of" if resume.experience_years else "professional"
        title_str = resume.current_title or "software developer"

        content = (
            f"I am a {title_str} with {exp_str} experience in {skills_str}. "
            f"I am applying for the {job.title} position at {job.company} "
            f"because I believe my background aligns well with your requirements.\n\n"
            f"Throughout my career, I have developed strong expertise in {skills_str}. "
            f"I am confident that these skills would allow me to contribute meaningfully "
            f"to {job.company}'s team from day one.\n\n"
            f"I would welcome the opportunity to discuss how my experience can benefit "
            f"{job.company}. Thank you for considering my application."
        )

        logger.warning(
            f"[cover_letter] Using fallback template for '{job.title}' at {job.company}"
        )

        return CoverLetter(
            job_id=job.id,
            content=content,
        )