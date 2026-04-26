import logging
import asyncio
from typing import Optional
from datetime import datetime
from backend.core.schemas import Resume

logger = logging.getLogger(__name__)


# ── Resume Store ───────────────────────────────────────────────────────────────

class ResumeStore:
    """
    In-memory singleton store for the active parsed resume.
    Single-user local app — one resume at a time.
    Thread-safe via asyncio lock.
    Tracks upload history for session context.
    """

    def __init__(self):
        self._resume: Optional[Resume] = None
        self._uploaded_at: Optional[datetime] = None
        self._filename: Optional[str] = None
        self._lock = asyncio.Lock()
        self._history: list[dict] = []          # lightweight upload audit trail

    # ── Core Operations ────────────────────────────────────────────────────────

    async def save(self, resume: Resume, filename: str = "unknown") -> None:
        """Store the parsed resume. Replaces any previously stored resume."""
        async with self._lock:
            self._resume = resume
            self._uploaded_at = datetime.now()
            self._filename = filename
            self._history.append({
                "filename": filename,
                "uploaded_at": self._uploaded_at.isoformat(),
                "skills_count": len(resume.skills),
                "experience_years": resume.experience_years,
                "current_title": resume.current_title,
            })
        logger.info(
            f"Resume stored: '{filename}' | "
            f"{len(resume.skills)} skills | "
            f"{resume.experience_years}yr exp | "
            f"title='{resume.current_title}'"
        )

    async def get(self) -> Optional[Resume]:
        """Get the currently stored resume. Returns None if not uploaded yet."""
        async with self._lock:
            return self._resume

    async def clear(self) -> None:
        """Clear the stored resume."""
        async with self._lock:
            self._resume = None
            self._uploaded_at = None
            self._filename = None
        logger.info("Resume store cleared")

    async def exists(self) -> bool:
        """Returns True if a resume is currently stored."""
        async with self._lock:
            return self._resume is not None

    # ── Metadata ───────────────────────────────────────────────────────────────

    async def get_meta(self) -> Optional[dict]:
        """Return metadata about the stored resume without the full text."""
        async with self._lock:
            if not self._resume:
                return None
            return {
                "filename": self._filename,
                "uploaded_at": self._uploaded_at.isoformat() if self._uploaded_at else None,
                "skills_count": len(self._resume.skills),
                "skills": self._resume.skills,
                "experience_years": self._resume.experience_years,
                "education": self._resume.education,
                "current_title": self._resume.current_title,
            }

    async def get_history(self) -> list[dict]:
        """Return upload history for the current session."""
        async with self._lock:
            return list(self._history)


# ── Singleton ──────────────────────────────────────────────────────────────────

resume_store = ResumeStore()