import logging
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
from typing import Optional
from backend.core.schemas import PipelineResult, PipelineStatus
from backend.agents.orchestrator import orchestrator
from backend.resume.resume_store import resume_store

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/pipeline", tags=["Pipeline"])


# ── Request / Response Models ──────────────────────────────────────────────────

class PipelineRunRequest(BaseModel):
    keywords: list[str] = Field(
        default=[],
        description="Job search keywords. If empty, auto-injected from resume skills.",
    )
    use_cache: bool = Field(
        default=True,
        description="Use cached jobs if available. Set False to force re-scrape.",
    )
    force_refresh: bool = Field(
        default=False,
        description="Force re-scrape even if cache is warm.",
    )
    generate_cover_letters: bool = Field(
        default=True,
        description="Generate cover letters for qualifying matches.",
    )


class PipelineStatusResponse(BaseModel):
    is_running: bool
    current_stage: Optional[str] = None
    timing_report: Optional[dict] = None


class PipelineRunResponse(BaseModel):
    message: str
    result: PipelineResult


# ── Routes ─────────────────────────────────────────────────────────────────────

@router.get(
    "/status",
    response_model=PipelineStatusResponse,
    summary="Get current pipeline status",
)
async def get_pipeline_status():
    """
    Returns whether the pipeline is currently running
    and timing from the last completed run.
    """
    return PipelineStatusResponse(
        is_running=orchestrator._is_running,
        current_stage=orchestrator._current_stage if orchestrator._is_running else None,
        timing_report=orchestrator.get_timing_report() if orchestrator._stage_times else None,
    )


@router.post(
    "/run",
    response_model=PipelineRunResponse,
    summary="Run the full pipeline",
    description=(
        "Runs the full 4-stage pipeline: scrape → match → score → draft. "
        "Blocks until complete. Use /ws/pipeline for real-time streaming."
    ),
)
async def run_pipeline(request: PipelineRunRequest):
    """
    Execute the full AI recruiter pipeline synchronously.

    Stages:
    1. Scraping — RemoteOK + HN + Adzuna
    2. Matching — Resume ↔ Job semantic matching
    3. Scoring  — Validate and normalize scores
    4. Drafting — Generate cover letters for qualifying jobs

    Returns complete PipelineResult with ranked JobWithScore list.

    Note: This is a blocking call. For real-time progress updates,
    connect to the WebSocket endpoint at /ws/pipeline instead.
    """
    # Guard: resume must be uploaded
    if not await resume_store.exists():
        raise HTTPException(
            status_code=400,
            detail=(
                "No resume uploaded. "
                "Upload your resume at POST /resume/upload before running the pipeline."
            ),
        )

    # Guard: pipeline already running
    if orchestrator._is_running:
        raise HTTPException(
            status_code=409,
            detail=(
                "Pipeline is already running. "
                "Wait for it to complete or connect to /ws/pipeline to monitor progress."
            ),
        )

    logger.info(
        f"[pipeline] POST /run — keywords={request.keywords}, "
        f"use_cache={request.use_cache}, "
        f"cover_letters={request.generate_cover_letters}"
    )

    try:
        result = await orchestrator.run(
            keywords=request.keywords,
            use_cache=request.use_cache and not request.force_refresh,
            generate_cover_letters=request.generate_cover_letters,
        )
    except ValueError as e:
        # Orchestrator raises ValueError for bad state (no resume etc.)
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"[pipeline] Run failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Pipeline execution failed: {str(e)}",
        )

    timing = orchestrator.get_timing_report()
    logger.info(
        f"[pipeline] Complete — "
        f"{result.total_jobs_scraped} scraped, "
        f"{result.total_jobs_matched} matched, "
        f"{len(result.results)} results | "
        f"total: {timing.get('total_seconds', '?')}s"
    )

    return PipelineRunResponse(
        message=(
            f"Pipeline complete in {timing.get('total_seconds', '?')}s. "
            f"{result.total_jobs_matched} jobs matched, "
            f"{sum(1 for r in result.results if r.cover_letter)} cover letters generated."
        ),
        result=result,
    )


@router.post(
    "/run/background",
    summary="Run pipeline in background",
    description=(
        "Fires the pipeline as a background task and returns immediately. "
        "Monitor progress via GET /pipeline/status or WebSocket /ws/pipeline."
    ),
)
async def run_pipeline_background(
    request: PipelineRunRequest,
    background_tasks: BackgroundTasks,
):
    """
    Start the pipeline as a background task.
    Returns immediately — pipeline runs asynchronously.
    Use GET /pipeline/status to poll, or /ws/pipeline for live updates.
    """
    if not await resume_store.exists():
        raise HTTPException(
            status_code=400,
            detail="No resume uploaded. Upload your resume first.",
        )

    if orchestrator._is_running:
        raise HTTPException(
            status_code=409,
            detail="Pipeline is already running.",
        )

    async def _run():
        try:
            await orchestrator.run(
                keywords=request.keywords,
                use_cache=request.use_cache and not request.force_refresh,
                generate_cover_letters=request.generate_cover_letters,
            )
        except Exception as e:
            logger.error(f"[pipeline] Background run failed: {e}")

    background_tasks.add_task(_run)

    logger.info("[pipeline] Pipeline started in background")
    return {
        "message": "Pipeline started in background.",
        "monitor": {
            "status_poll": "GET /pipeline/status",
            "live_stream": "WS /ws/pipeline",
        },
    }


@router.get(
    "/results",
    summary="Get results from last pipeline run",
    description="Returns the assembled PipelineResult from the last completed run.",
)
async def get_last_results():
    """
    Returns results from the most recent pipeline run.
    Raises 404 if pipeline has never been run this session.
    """
    if orchestrator._is_running:
        raise HTTPException(
            status_code=409,
            detail="Pipeline is currently running. Results will be available when complete.",
        )

    if not orchestrator._stage_times:
        raise HTTPException(
            status_code=404,
            detail="No pipeline results available. Run the pipeline first.",
        )

    return {
        "timing": orchestrator.get_timing_report(),
        "message": "Use POST /pipeline/run to get full results with job data.",
    }


@router.get(
    "/timing",
    summary="Get timing report from last run",
)
async def get_timing_report():
    """Returns per-stage timing from the last pipeline run."""
    if not orchestrator._stage_times:
        raise HTTPException(
            status_code=404,
            detail="No timing data available. Run the pipeline first.",
        )
    return orchestrator.get_timing_report()