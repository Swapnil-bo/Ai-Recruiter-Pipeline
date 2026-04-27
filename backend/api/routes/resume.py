import logging
from pathlib import Path
from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel
from typing import Optional
from backend.core.schemas import Resume
from backend.resume.parser import ResumeParser, ResumeParseError, UnsupportedFileTypeError, EmptyResumeError
from backend.resume.resume_store import resume_store

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/resume", tags=["Resume"])

# ── Constants ──────────────────────────────────────────────────────────────────

MAX_FILE_SIZE_MB = 5
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024
ALLOWED_EXTENSIONS = {".pdf", ".txt", ".md"}
ALLOWED_MIME_TYPES = {
    "application/pdf",
    "text/plain",
    "text/markdown",
    "application/octet-stream",     # some clients send this for .md
}


# ── Request / Response Models ──────────────────────────────────────────────────

class ResumeMeta(BaseModel):
    filename: str
    uploaded_at: Optional[str]
    skills_count: int
    skills: list[str]
    experience_years: Optional[float]
    education: Optional[str]
    current_title: Optional[str]


class ResumeTextRequest(BaseModel):
    text: str
    filename: str = "resume.txt"


class ResumeStatusResponse(BaseModel):
    uploaded: bool
    meta: Optional[ResumeMeta] = None


# ── Routes ─────────────────────────────────────────────────────────────────────

@router.get(
    "/status",
    response_model=ResumeStatusResponse,
    summary="Check if resume is uploaded",
)
async def get_resume_status():
    """
    Check if a resume is currently stored.
    Returns metadata if uploaded, uploaded=False otherwise.
    """
    exists = await resume_store.exists()
    if not exists:
        return ResumeStatusResponse(uploaded=False)

    meta = await resume_store.get_meta()
    return ResumeStatusResponse(
        uploaded=True,
        meta=ResumeMeta(**meta) if meta else None,
    )


@router.get(
    "/",
    response_model=Resume,
    summary="Get the stored resume",
)
async def get_resume():
    """
    Returns the full parsed resume currently in store.
    Raises 404 if no resume has been uploaded yet.
    """
    resume = await resume_store.get()
    if not resume:
        raise HTTPException(
            status_code=404,
            detail="No resume uploaded. Use POST /resume/upload to upload one.",
        )
    return resume


@router.post(
    "/upload",
    response_model=ResumeMeta,
    summary="Upload and parse a resume file",
    description="Accepts PDF, TXT, or MD files up to 5MB.",
)
async def upload_resume(file: UploadFile = File(...)):
    """
    Upload a resume file for parsing.

    - Validates file type and size
    - Extracts text (PDF via PyMuPDF, text files directly)
    - Runs rule-based + LLM parsing pipeline
    - Stores parsed resume in memory for pipeline use

    Supported formats: .pdf, .txt, .md
    Max size: 5MB
    """
    logger.info(f"[resume] Upload received: {file.filename} ({file.content_type})")

    # ── Validate filename ──────────────────────────────────────────────────────
    if not file.filename:
        raise HTTPException(status_code=422, detail="Filename is required.")

    ext = _get_extension(file.filename)
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=415,
            detail=(
                f"Unsupported file type: '{ext}'. "
                f"Allowed: {', '.join(ALLOWED_EXTENSIONS)}"
            ),
        )

    # ── MIME type warning — don't hard reject, extension check is more reliable
    if file.content_type and file.content_type not in ALLOWED_MIME_TYPES:
        logger.warning(
            f"[resume] Unexpected MIME type: {file.content_type} "
            f"for file {file.filename} — proceeding with extension check"
        )

    # ── Read and validate size ─────────────────────────────────────────────────
    try:
        file_bytes = await file.read()
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to read uploaded file: {e}",
        )

    if len(file_bytes) == 0:
        raise HTTPException(status_code=422, detail="Uploaded file is empty.")

    if len(file_bytes) > MAX_FILE_SIZE_BYTES:
        size_mb = len(file_bytes) / (1024 * 1024)
        raise HTTPException(
            status_code=413,
            detail=(
                f"File too large: {size_mb:.1f}MB. "
                f"Maximum allowed: {MAX_FILE_SIZE_MB}MB."
            ),
        )

    # ── Parse ──────────────────────────────────────────────────────────────────
    parser = ResumeParser()
    try:
        resume = await parser.parse_bytes(file_bytes, file.filename)
    except UnsupportedFileTypeError as e:
        raise HTTPException(status_code=415, detail=str(e))
    except EmptyResumeError as e:
        raise HTTPException(
            status_code=422,
            detail=f"Could not extract text from resume: {e}",
        )
    except ResumeParseError as e:
        raise HTTPException(
            status_code=422,
            detail=f"Resume parsing failed: {e}",
        )
    except Exception as e:
        logger.error(f"[resume] Unexpected parse error: {e}")
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred while parsing the resume.",
        )

    # ── Store ──────────────────────────────────────────────────────────────────
    await resume_store.save(resume, filename=file.filename)

    meta = await resume_store.get_meta()
    logger.info(
        f"[resume] Stored: {file.filename} | "
        f"{len(resume.skills)} skills | "
        f"{resume.experience_years}yr | "
        f"'{resume.current_title}'"
    )

    return ResumeMeta(**meta)


@router.post(
    "/upload/text",
    response_model=ResumeMeta,
    summary="Upload resume as plain text",
    description="Accepts raw resume text directly — useful for testing.",
)
async def upload_resume_text(request: ResumeTextRequest):
    """
    Upload resume as raw text string instead of a file.
    Useful for testing or when user wants to paste resume content directly.
    """
    logger.info(f"[resume] Text upload: {len(request.text)} chars")

    if not request.text or not request.text.strip():
        raise HTTPException(status_code=422, detail="Resume text cannot be empty.")

    if len(request.text) < 100:
        raise HTTPException(
            status_code=422,
            detail="Resume text too short. Minimum 100 characters.",
        )

    if len(request.text) > 50_000:
        raise HTTPException(
            status_code=413,
            detail="Resume text too long. Maximum 50,000 characters.",
        )

    parser = ResumeParser()
    try:
        resume = await parser.parse_text(request.text)
    except EmptyResumeError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error(f"[resume] Text parse error: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to parse resume text.",
        )

    await resume_store.save(resume, filename=request.filename)

    meta = await resume_store.get_meta()
    return ResumeMeta(**meta)


@router.delete(
    "/",
    summary="Clear stored resume",
)
async def clear_resume():
    """Remove the currently stored resume from memory."""
    exists = await resume_store.exists()
    if not exists:
        raise HTTPException(
            status_code=404,
            detail="No resume is currently stored.",
        )
    await resume_store.clear()
    logger.info("[resume] Resume cleared from store")
    return {"message": "Resume cleared successfully."}


@router.get(
    "/history",
    summary="Get upload history",
    description="Returns a log of all resume uploads in the current session.",
)
async def get_upload_history():
    """Returns the upload history for the current session."""
    history = await resume_store.get_history()
    return {
        "total_uploads": len(history),
        "history": history,
    }


# ── Helpers ────────────────────────────────────────────────────────────────────

def _get_extension(filename: str) -> str:
    """Extract lowercase file extension including the dot."""
    return Path(filename).suffix.lower()