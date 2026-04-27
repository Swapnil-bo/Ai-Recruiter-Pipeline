import asyncio
import logging
import time
from typing import Optional, Callable, AsyncGenerator
from backend.core.schemas import (
    Job, Resume, MatchResult, CoverLetter,
    PipelineStatus, PipelineResult, JobWithScore,
)
from backend.core.config import settings
from backend.agents.matcher_agent import MatcherAgent
from backend.agents.scorer_agent import ScorerAgent
from backend.agents.cover_letter_agent import CoverLetterAgent
from backend.scraper.remoteok_scraper import RemoteOKScraper
from backend.scraper.hn_scraper import HNScraper
from backend.scraper.adzuna_scraper import AdzunaScraper
from backend.resume.resume_store import resume_store
from backend.utils.cache import job_cache

logger = logging.getLogger(__name__)


# ── Pipeline Stages ────────────────────────────────────────────────────────────

STAGE_SCRAPING      = "scraping"
STAGE_MATCHING      = "matching"
STAGE_SCORING       = "scoring"
STAGE_DRAFTING      = "drafting"
STAGE_DONE          = "done"
STAGE_ERROR         = "error"


# ── Orchestrator ───────────────────────────────────────────────────────────────

class PipelineOrchestrator:
    """
    Master controller for the AI Recruiter Pipeline.

    Pipeline flow:
    ┌─────────────────────────────────────────────────────┐
    │  Stage 1: SCRAPING                                  │
    │  RemoteOK + HN + Adzuna → deduplicated Job list     │
    ├─────────────────────────────────────────────────────┤
    │  Stage 2: MATCHING                                  │
    │  MatcherAgent → MatchResult per job (rule + LLM)    │
    ├─────────────────────────────────────────────────────┤
    │  Stage 3: SCORING                                   │
    │  ScorerAgent → validated + normalized MatchResults  │
    ├─────────────────────────────────────────────────────┤
    │  Stage 4: DRAFTING                                  │
    │  CoverLetterAgent → CoverLetter per qualifying job  │
    ├─────────────────────────────────────────────────────┤
    │  Stage 5: DONE                                      │
    │  PipelineResult → sorted JobWithScore list          │
    └─────────────────────────────────────────────────────┘

    Features:
    - Real-time progress via async generator (WebSocket-ready)
    - Per-stage timing and telemetry
    - Graceful partial failure — pipeline never fully crashes
    - Resume from cache if jobs already scraped
    - Configurable keyword injection from resume skills
    """

    def __init__(
        self,
        matcher:      Optional[MatcherAgent]      = None,
        scorer:       Optional[ScorerAgent]       = None,
        cover_letter: Optional[CoverLetterAgent]  = None,
    ):
        self._matcher      = matcher      or MatcherAgent()
        self._scorer       = scorer       or ScorerAgent()
        self._cover_letter = cover_letter or CoverLetterAgent()

        # Pipeline state — reset per run
        self._current_stage: str = STAGE_DONE
        self._is_running:    bool = False
        self._start_time:    float = 0.0
        self._stage_times:   dict[str, float] = {}
        self._last_result:   Optional[PipelineResult] = None

    # ── Public Properties ──────────────────────────────────────────────────────

    @property
    def is_running(self) -> bool:
        """Returns True if the pipeline is currently executing."""
        return self._is_running

    @property
    def current_stage(self) -> str:
        """Returns the name of the currently executing stage."""
        return self._current_stage

    @property
    def has_run(self) -> bool:
        """Returns True if the pipeline has completed at least one run."""
        return bool(self._stage_times)

    # ── Public API ─────────────────────────────────────────────────────────────

    async def run(
        self,
        keywords: list[str],
        use_cache: bool = True,
        generate_cover_letters: bool = True,
        on_status: Optional[Callable[[PipelineStatus], None]] = None,
    ) -> PipelineResult:
        """
        Run the full pipeline synchronously (non-streaming).
        on_status callback fires on each stage transition.

        Args:
            keywords: Job search keywords
            use_cache: Skip scraping if cached jobs available
            generate_cover_letters: Run cover letter stage
            on_status: Optional status callback

        Returns:
            PipelineResult with all scored jobs and cover letters
        """
        if self._is_running:
            raise RuntimeError("Pipeline is already running. Wait for it to complete.")

        self._is_running = True
        self._start_time = time.time()
        self._stage_times = {}

        try:
            return await self._execute_pipeline(
                keywords=keywords,
                use_cache=use_cache,
                generate_cover_letters=generate_cover_letters,
                on_status=on_status,
            )
        finally:
            self._is_running = False

    async def stream(
        self,
        keywords: list[str],
        use_cache: bool = True,
        generate_cover_letters: bool = True,
    ) -> AsyncGenerator[PipelineStatus, None]:
        """
        Run pipeline and yield PipelineStatus updates as they happen.
        Designed for WebSocket streaming to frontend.

        Usage:
            async for status in orchestrator.stream(keywords):
                await websocket.send_json(status.model_dump())
        """
        if self._is_running:
            yield PipelineStatus(
                stage=STAGE_ERROR,
                progress=0,
                message="Pipeline already running",
            )
            return

        self._is_running = True
        self._start_time = time.time()
        self._stage_times = {}

        status_queue: asyncio.Queue[Optional[PipelineStatus]] = asyncio.Queue()

        async def status_callback(status: PipelineStatus):
            await status_queue.put(status)

        async def run_pipeline():
            try:
                await self._execute_pipeline(
                    keywords=keywords,
                    use_cache=use_cache,
                    generate_cover_letters=generate_cover_letters,
                    on_status=status_callback,
                )
            except Exception as e:
                await status_queue.put(PipelineStatus(
                    stage=STAGE_ERROR,
                    progress=0,
                    message=f"Pipeline error: {str(e)}",
                ))
            finally:
                self._is_running = False
                await status_queue.put(None)     # sentinel

        pipeline_task = asyncio.create_task(run_pipeline())

        try:
            while True:
                status = await status_queue.get()
                if status is None:
                    break
                yield status
        finally:
            if not pipeline_task.done():
                pipeline_task.cancel()

    # ── Pipeline Execution ─────────────────────────────────────────────────────

    async def _execute_pipeline(
        self,
        keywords: list[str],
        use_cache: bool,
        generate_cover_letters: bool,
        on_status: Optional[Callable],
    ) -> PipelineResult:
        """Core pipeline execution. Called by both run() and stream()."""

        resume = await resume_store.get()
        if not resume:
            raise ValueError(
                "No resume uploaded. Upload a resume before running the pipeline."
            )

        # Auto-inject resume skills into keywords if not enough keywords
        effective_keywords = self._build_keywords(keywords, resume)
        logger.info(f"[orchestrator] Keywords: {effective_keywords}")

        # ── Stage 1: Scraping ──────────────────────────────────────────────────
        jobs = await self._stage_scraping(
            keywords=effective_keywords,
            use_cache=use_cache,
            on_status=on_status,
        )

        if not jobs:
            logger.warning("[orchestrator] No jobs scraped — returning empty result")
            await self._emit(on_status, PipelineStatus(
                stage=STAGE_DONE,
                progress=100,
                message="No jobs found. Try different keywords.",
                jobs_processed=0,
                total_jobs=0,
            ))
            result = PipelineResult(
                total_jobs_scraped=0,
                total_jobs_matched=0,
                results=[],
            )
            self._last_result = result
            return result

        # ── Stage 2: Matching ──────────────────────────────────────────────────
        matches = await self._stage_matching(
            resume=resume,
            jobs=jobs,
            on_status=on_status,
        )

        if not matches:
            logger.warning("[orchestrator] No matches found")
            await self._emit(on_status, PipelineStatus(
                stage=STAGE_DONE,
                progress=100,
                message="No relevant jobs matched your resume.",
                jobs_processed=len(jobs),
                total_jobs=len(jobs),
            ))
            result = PipelineResult(
                total_jobs_scraped=len(jobs),
                total_jobs_matched=0,
                results=[],
            )
            self._last_result = result
            return result

        # ── Stage 3: Scoring ───────────────────────────────────────────────────
        scored_matches = await self._stage_scoring(
            resume=resume,
            jobs=jobs,
            matches=matches,
            on_status=on_status,
        )

        # ── Stage 4: Cover Letter Drafting ─────────────────────────────────────
        cover_letters: list[CoverLetter] = []
        if generate_cover_letters:
            cover_letters = await self._stage_drafting(
                resume=resume,
                jobs=jobs,
                matches=scored_matches,
                on_status=on_status,
            )

        # ── Stage 5: Assemble Result ───────────────────────────────────────────
        result = self._assemble_result(jobs, scored_matches, cover_letters)
        self._last_result = result

        elapsed = round(time.time() - self._start_time, 1)
        logger.info(
            f"[orchestrator] Pipeline complete in {elapsed}s — "
            f"{result.total_jobs_scraped} scraped, "
            f"{result.total_jobs_matched} matched, "
            f"{len(cover_letters)} cover letters"
        )

        await self._emit(on_status, PipelineStatus(
            stage=STAGE_DONE,
            progress=100,
            message=(
                f"Done in {elapsed}s — "
                f"{result.total_jobs_matched} matches, "
                f"{len(cover_letters)} cover letters generated"
            ),
            jobs_processed=result.total_jobs_matched,
            total_jobs=result.total_jobs_scraped,
        ))

        return result

    # ── Stage Implementations ──────────────────────────────────────────────────

    async def _stage_scraping(
        self,
        keywords: list[str],
        use_cache: bool,
        on_status: Optional[Callable],
    ) -> list[Job]:
        stage_start = time.time()

        await self._emit(on_status, PipelineStatus(
            stage=STAGE_SCRAPING,
            progress=0,
            message="Checking cache...",
        ))

        # Try cache first
        if use_cache:
            cached = await job_cache.get_all()
            if cached:
                logger.info(f"[orchestrator] Loaded {len(cached)} jobs from cache")
                await self._emit(on_status, PipelineStatus(
                    stage=STAGE_SCRAPING,
                    progress=100,
                    message=f"Loaded {len(cached)} jobs from cache",
                    total_jobs=len(cached),
                ))
                self._stage_times[STAGE_SCRAPING] = time.time() - stage_start
                return cached

        await self._emit(on_status, PipelineStatus(
            stage=STAGE_SCRAPING,
            progress=10,
            message="Scraping RemoteOK, HN, and Adzuna...",
        ))

        # Run all scrapers concurrently
        remoteok_jobs, hn_jobs, adzuna_jobs = await asyncio.gather(
            self._scrape_source(RemoteOKScraper, keywords),
            self._scrape_source(HNScraper, keywords),
            self._scrape_source(AdzunaScraper, keywords),
        )

        await self._emit(on_status, PipelineStatus(
            stage=STAGE_SCRAPING,
            progress=70,
            message="Deduplicating results...",
        ))

        # Merge and deduplicate
        all_jobs = self._deduplicate_jobs(remoteok_jobs + hn_jobs + adzuna_jobs)

        # Cache results
        if all_jobs:
            await job_cache.set_many(all_jobs)
            await job_cache.save_to_disk()

        self._stage_times[STAGE_SCRAPING] = time.time() - stage_start

        await self._emit(on_status, PipelineStatus(
            stage=STAGE_SCRAPING,
            progress=100,
            message=f"Scraped {len(all_jobs)} jobs from 3 sources",
            total_jobs=len(all_jobs),
        ))

        logger.info(
            f"[orchestrator] Scraping done: {len(remoteok_jobs)} RemoteOK + "
            f"{len(hn_jobs)} HN + {len(adzuna_jobs)} Adzuna = "
            f"{len(all_jobs)} unique jobs "
            f"({self._stage_times[STAGE_SCRAPING]:.1f}s)"
        )

        return all_jobs

    async def _stage_matching(
        self,
        resume: Resume,
        jobs: list[Job],
        on_status: Optional[Callable],
    ) -> list[MatchResult]:
        stage_start = time.time()

        await self._emit(on_status, PipelineStatus(
            stage=STAGE_MATCHING,
            progress=0,
            message=f"Matching resume against {len(jobs)} jobs...",
            total_jobs=len(jobs),
        ))

        completed_count = 0

        async def on_progress(completed: int, total: int):
            nonlocal completed_count
            completed_count = completed
            pct = int((completed / total) * 100)
            await self._emit(on_status, PipelineStatus(
                stage=STAGE_MATCHING,
                progress=pct,
                message=f"Matching job {completed}/{total}...",
                jobs_processed=completed,
                total_jobs=total,
            ))

        matches = await self._matcher.match_many(
            resume=resume,
            jobs=jobs,
            on_progress=on_progress,
        )

        self._stage_times[STAGE_MATCHING] = time.time() - stage_start

        await self._emit(on_status, PipelineStatus(
            stage=STAGE_MATCHING,
            progress=100,
            message=f"Matched {len(matches)} relevant jobs",
            jobs_processed=len(matches),
            total_jobs=len(jobs),
        ))

        logger.info(
            f"[orchestrator] Matching done: {len(matches)}/{len(jobs)} matched "
            f"({self._stage_times[STAGE_MATCHING]:.1f}s)"
        )

        return matches

    async def _stage_scoring(
        self,
        resume: Resume,
        jobs: list[Job],
        matches: list[MatchResult],
        on_status: Optional[Callable],
    ) -> list[MatchResult]:
        stage_start = time.time()

        await self._emit(on_status, PipelineStatus(
            stage=STAGE_SCORING,
            progress=0,
            message=f"Scoring {len(matches)} matches...",
            total_jobs=len(matches),
        ))

        async def on_progress(completed: int, total: int):
            pct = int((completed / total) * 100)
            await self._emit(on_status, PipelineStatus(
                stage=STAGE_SCORING,
                progress=pct,
                message=f"Scoring match {completed}/{total}...",
                jobs_processed=completed,
                total_jobs=total,
            ))

        scored = await self._scorer.score_many(
            resume=resume,
            jobs=jobs,
            matches=matches,
            on_progress=on_progress,
        )

        self._stage_times[STAGE_SCORING] = time.time() - stage_start

        top = scored[0] if scored else None
        await self._emit(on_status, PipelineStatus(
            stage=STAGE_SCORING,
            progress=100,
            message=(
                f"Scoring complete. Top match: {top.fit_score:.1f}/10"
                if top else "Scoring complete"
            ),
            jobs_processed=len(scored),
            total_jobs=len(matches),
        ))

        logger.info(
            f"[orchestrator] Scoring done ({self._stage_times[STAGE_SCORING]:.1f}s)"
        )

        return scored

    async def _stage_drafting(
        self,
        resume: Resume,
        jobs: list[Job],
        matches: list[MatchResult],
        on_status: Optional[Callable],
    ) -> list[CoverLetter]:
        stage_start = time.time()

        qualifying_count = sum(
            1 for m in matches
            if m.fit_score >= self._cover_letter.MIN_FIT_SCORE_FOR_GENERATION
        )

        await self._emit(on_status, PipelineStatus(
            stage=STAGE_DRAFTING,
            progress=0,
            message=f"Drafting cover letters for {qualifying_count} qualifying jobs...",
            total_jobs=qualifying_count,
        ))

        async def on_progress(completed: int, total: int):
            pct = int((completed / total) * 100) if total > 0 else 100
            await self._emit(on_status, PipelineStatus(
                stage=STAGE_DRAFTING,
                progress=pct,
                message=f"Drafting cover letter {completed}/{total}...",
                jobs_processed=completed,
                total_jobs=total,
            ))

        cover_letters = await self._cover_letter.generate_many(
            resume=resume,
            jobs=jobs,
            matches=matches,
            on_progress=on_progress,
        )

        self._stage_times[STAGE_DRAFTING] = time.time() - stage_start

        await self._emit(on_status, PipelineStatus(
            stage=STAGE_DRAFTING,
            progress=100,
            message=f"{len(cover_letters)} cover letters drafted",
            jobs_processed=len(cover_letters),
            total_jobs=qualifying_count,
        ))

        logger.info(
            f"[orchestrator] Drafting done: {len(cover_letters)} cover letters "
            f"({self._stage_times[STAGE_DRAFTING]:.1f}s)"
        )

        return cover_letters

    # ── Helpers ────────────────────────────────────────────────────────────────

    async def _scrape_source(
        self,
        scraper_class,
        keywords: list[str],
    ) -> list[Job]:
        """Run a single scraper safely — returns [] on any failure."""
        try:
            async with scraper_class() as scraper:
                return await scraper.scrape(keywords)
        except Exception as e:
            logger.error(f"[orchestrator] {scraper_class.__name__} failed: {e}")
            return []

    def _deduplicate_jobs(self, jobs: list[Job]) -> list[Job]:
        """Deduplicate jobs by ID. Preserves first occurrence."""
        seen: set[str] = set()
        unique: list[Job] = []
        for job in jobs:
            if job.id not in seen:
                seen.add(job.id)
                unique.append(job)
        duplicates = len(jobs) - len(unique)
        if duplicates:
            logger.info(f"[orchestrator] Removed {duplicates} duplicate jobs")
        return unique

    def _build_keywords(self, keywords: list[str], resume: Resume) -> list[str]:
        """
        Merge user-provided keywords with top resume skills.
        Ensures pipeline always has meaningful search terms.
        """
        combined = list(keywords)

        if resume.skills and len(combined) < 3:
            # Inject top skills as keywords if user provided too few
            top_skills = resume.skills[:5]
            for skill in top_skills:
                if skill.lower() not in [k.lower() for k in combined]:
                    combined.append(skill)
            logger.info(f"[orchestrator] Auto-injected skills as keywords: {top_skills}")

        if resume.current_title and resume.current_title.lower() not in [k.lower() for k in combined]:
            combined.insert(0, resume.current_title)

        return combined[:10]                 # cap at 10 keywords

    def _assemble_result(
        self,
        jobs: list[Job],
        matches: list[MatchResult],
        cover_letters: list[CoverLetter],
    ) -> PipelineResult:
        """
        Assemble final PipelineResult.
        Joins jobs + matches + cover letters by job_id.
        Sorted by fit_score descending.
        """
        job_map: dict[str, Job]           = {j.id: j for j in jobs}
        match_map: dict[str, MatchResult] = {m.job_id: m for m in matches}
        cl_map: dict[str, CoverLetter]    = {c.job_id: c for c in cover_letters}

        results: list[JobWithScore] = []
        for job_id, match in match_map.items():
            job = job_map.get(job_id)
            if not job:
                continue
            results.append(JobWithScore(
                job=job,
                match=match,
                cover_letter=cl_map.get(job_id),
            ))

        results.sort(key=lambda r: r.match.fit_score if r.match else 0, reverse=True)

        return PipelineResult(
            total_jobs_scraped=len(jobs),
            total_jobs_matched=len(matches),
            results=results,
        )

    @staticmethod
    async def _emit(
        callback: Optional[Callable],
        status: PipelineStatus,
    ) -> None:
        """Fire status callback safely — never raises."""
        if not callback:
            return
        try:
            if asyncio.iscoroutinefunction(callback):
                await callback(status)
            else:
                callback(status)
        except Exception as e:
            logger.warning(f"[orchestrator] Status callback error: {e}")

    # ── Telemetry ──────────────────────────────────────────────────────────────

    def get_timing_report(self) -> dict:
        """Returns per-stage timing from the last pipeline run."""
        total = sum(self._stage_times.values())
        return {
            "stages": self._stage_times,
            "total_seconds": round(total, 1),
        }

    def get_last_result(self) -> Optional[PipelineResult]:
        """Returns the PipelineResult from the last completed run, or None."""
        return self._last_result


# ── Singleton ──────────────────────────────────────────────────────────────────

orchestrator = PipelineOrchestrator()