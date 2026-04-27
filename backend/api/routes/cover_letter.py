import asyncio
import logging
from fastapi import APIRouter, HTTPException
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field
from typing import Optional
from backend.core.schemas import CoverLetter
from backend.agents.cover_letter_agent import CoverLetterAgent
from backend.resume.resume_store import resume_store
from backend.utils.cache import job_cache

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/cover-letter", tags=["Cover Letter"])

# ── Session Store ──────────────────────────────────────────────────────────────
# Lightweight in-memory store — keyed by job_id
_cover_letter_store: dict[str, CoverLetter] = {}
_store_lock = asyncio.Lock()

# ── Module-level agent singleton ───────────────────────────────────────────────
_agent = CoverLetterAgent()


# ── Request / Response Models ──────────────────────────────────────────────────

class GenerateRequest(BaseModel):
    job_id: str = Field(description="ID of the job to generate a cover letter for.")
    fit_score: float = Field(
        ge=0.0,
        le=10.0,
        description="Fit score for this job (from scorer agent).",
    )
    force_regenerate: bool = Field(
        default=False,
        description="Regenerate even if a cover letter already exists for this job.",
    )


class UpdateRequest(BaseModel):
    content: str = Field(
        min_length=50,
        max_length=5000,
        description="Updated cover letter content.",
    )


class CoverLetterResponse(BaseModel):
    job_id: str
    content: str
    generated_at: str
    word_count: int
    is_edited: bool = False


class CoverLetterListResponse(BaseModel):
    total: int
    cover_letters: list[CoverLetterResponse]


# ── Routes ─────────────────────────────────────────────────────────────────────

@router.get(
    "/",
    response_model=CoverLetterListResponse,
    summary="Get all generated cover letters",
)
async def get_all_cover_letters():
    """
    Returns all cover letters generated in the current session.
    Sorted by generated_at descending (newest first).
    """
    if not _cover_letter_store:
        return CoverLetterListResponse(total=0, cover_letters=[])

    sorted_cls = sorted(
        _cover_letter_store.values(),
        key=lambda c: c.generated_at,
        reverse=True,
    )

    return CoverLetterListResponse(
        total=len(sorted_cls),
        cover_letters=[_to_response(cl) for cl in sorted_cls],
    )


@router.post(
    "/generate",
    response_model=CoverLetterResponse,
    summary="Generate a cover letter for a job",
    description=(
        "Generates a tailored cover letter using the stored resume and job details. "
        "Job must exist in cache. Resume must be uploaded."
    ),
)
async def generate_cover_letter(request: GenerateRequest):
    """
    Generate a tailored cover letter for a specific job.

    Requirements:
    - Resume must be uploaded (POST /resume/upload)
    - Job must exist in job cache (run pipeline or POST /jobs/scrape first)
    - fit_score must be provided (from pipeline results)

    Returns the generated cover letter with word count.
    Stores result in session for future retrieval.
    """
    # ── Guard: existing cover letter ───────────────────────────────────────────
    if not request.force_regenerate and request.job_id in _cover_letter_store:
        logger.info(f"[cover_letter] Returning cached cover letter for {request.job_id}")
        return _to_response(_cover_letter_store[request.job_id])

    # ── Guard: resume ──────────────────────────────────────────────────────────
    resume = await resume_store.get()
    if not resume:
        raise HTTPException(
            status_code=400,
            detail="No resume uploaded. Upload your resume at POST /resume/upload first.",
        )

    # ── Guard: job exists ──────────────────────────────────────────────────────
    job = await job_cache.get(request.job_id)
    if not job:
        raise HTTPException(
            status_code=404,
            detail=(
                f"Job '{request.job_id}' not found in cache. "
                f"Run the pipeline or POST /jobs/scrape first."
            ),
        )

    # ── Guard: fit score too low ───────────────────────────────────────────────
    if request.fit_score < _agent.MIN_FIT_SCORE_FOR_GENERATION:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Fit score {request.fit_score:.1f} is below the minimum threshold "
                f"({_agent.MIN_FIT_SCORE_FOR_GENERATION}). "
                f"Cover letters are only generated for strong matches."
            ),
        )

    logger.info(
        f"[cover_letter] Generating for job '{request.job_id}' "
        f"(fit: {request.fit_score:.1f})"
    )

    # ── Generate ───────────────────────────────────────────────────────────────
    cover_letter = await _agent.generate_one(
        resume=resume,
        job=job,
        fit_score=request.fit_score,
    )

    if not cover_letter:
        raise HTTPException(
            status_code=500,
            detail="Cover letter generation failed. Try again or check Ollama is running.",
        )

    # ── Store ──────────────────────────────────────────────────────────────────
    async with _store_lock:
        _cover_letter_store[request.job_id] = cover_letter

    logger.info(
        f"[cover_letter] Generated for '{job.title}' at {job.company} — "
        f"{len(cover_letter.content.split())} words"
    )

    return _to_response(cover_letter)


# ── Static routes MUST come before /{job_id} to avoid route conflicts ──────────

@router.delete(
    "/",
    summary="Clear all cover letters",
)
async def clear_all_cover_letters():
    """Clear all cover letters from the session store."""
    async with _store_lock:
        count = len(_cover_letter_store)
        _cover_letter_store.clear()
    logger.info(f"[cover_letter] Cleared {count} cover letters")
    return {
        "message": "All cover letters cleared.",
        "deleted": count,
    }


@router.get(
    "/{job_id}",
    response_model=CoverLetterResponse,
    summary="Get cover letter for a specific job",
)
async def get_cover_letter(job_id: str):
    """
    Retrieve the cover letter for a specific job by job ID.
    Raises 404 if not yet generated.
    """
    cl = _cover_letter_store.get(job_id)
    if not cl:
        raise HTTPException(
            status_code=404,
            detail=(
                f"No cover letter found for job '{job_id}'. "
                f"Generate one via POST /cover-letter/generate."
            ),
        )
    return _to_response(cl)


@router.get(
    "/{job_id}/text",
    response_class=PlainTextResponse,
    summary="Get cover letter as plain text",
    description="Returns just the raw cover letter text — useful for copy-paste.",
)
async def get_cover_letter_text(job_id: str):
    """Returns the cover letter content as plain text."""
    cl = _cover_letter_store.get(job_id)
    if not cl:
        raise HTTPException(
            status_code=404,
            detail=f"No cover letter found for job '{job_id}'.",
        )
    return cl.content


@router.put(
    "/{job_id}",
    response_model=CoverLetterResponse,
    summary="Update a cover letter",
    description="Replace the content of an existing cover letter with edited text.",
)
async def update_cover_letter(job_id: str, request: UpdateRequest):
    """
    Update the content of an existing cover letter.
    Used when user edits the generated text in the frontend editor.
    Marks the cover letter as edited.
    """
    async with _store_lock:
        if job_id not in _cover_letter_store:
            raise HTTPException(
                status_code=404,
                detail=f"No cover letter found for job '{job_id}'. Generate one first.",
            )

        existing = _cover_letter_store[job_id]

        # Replace content, preserve job_id and generated_at
        updated = CoverLetter(
            job_id=existing.job_id,
            content=request.content.strip(),
            generated_at=existing.generated_at,
        )
        _cover_letter_store[job_id] = updated

    logger.info(
        f"[cover_letter] Updated for job '{job_id}' — "
        f"{len(updated.content.split())} words"
    )

    return _to_response(updated, is_edited=True)


@router.delete(
    "/{job_id}",
    summary="Delete a cover letter",
)
async def delete_cover_letter(job_id: str):
    """Delete a specific cover letter from the session store."""
    async with _store_lock:
        if job_id not in _cover_letter_store:
            raise HTTPException(
                status_code=404,
                detail=f"No cover letter found for job '{job_id}'.",
            )
        del _cover_letter_store[job_id]

    logger.info(f"[cover_letter] Deleted cover letter for job '{job_id}'")
    return {"message": f"Cover letter for job '{job_id}' deleted."}


# ── Helpers ────────────────────────────────────────────────────────────────────

def _to_response(cl: CoverLetter, is_edited: bool = False) -> CoverLetterResponse:
    """Convert CoverLetter schema to CoverLetterResponse."""
    return CoverLetterResponse(
        job_id=cl.job_id,
        content=cl.content,
        generated_at=str(cl.generated_at),
        word_count=len(cl.content.split()),
        is_edited=is_edited,
    )