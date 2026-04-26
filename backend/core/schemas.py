from pydantic import BaseModel, HttpUrl, Field
from typing import Optional, Literal
from datetime import datetime

# ── Job ────────────────────────────────────────────────────────────────────────
class Job(BaseModel):
    id: str
    title: str
    company: str
    location: str
    description: str
    url: HttpUrl
    source: str                          # remoteok | hn | adzuna
    salary: Optional[str] = None
    tags: list[str] = []
    posted_at: Optional[str] = None
    scraped_at: datetime = Field(default_factory=datetime.now)

# ── Resume ─────────────────────────────────────────────────────────────────────
class Resume(BaseModel):
    raw_text: str
    skills: list[str] = []
    experience_years: Optional[float] = None
    education: Optional[str] = None
    current_title: Optional[str] = None
    parsed_at: datetime = Field(default_factory=datetime.now)

# ── Match Result ───────────────────────────────────────────────────────────────
class MatchResult(BaseModel):
    job_id: str
    fit_score: float = Field(ge=0.0, le=10.0)
    score_breakdown: dict[str, float]    # skills, experience, role, culture
    matched_skills: list[str]
    missing_skills: list[str]
    reasoning: str

# ── Cover Letter ───────────────────────────────────────────────────────────────
class CoverLetter(BaseModel):
    job_id: str
    content: str
    generated_at: datetime = Field(default_factory=datetime.now)

# ── Pipeline ───────────────────────────────────────────────────────────────────
class PipelineStatus(BaseModel):
    stage: Literal["scraping", "matching", "scoring", "drafting", "done"]
    progress: int = Field(ge=0, le=100)
    message: str
    jobs_processed: int = 0
    total_jobs: int = 0

# ── API Response Wrappers ──────────────────────────────────────────────────────
class JobWithScore(BaseModel):
    job: Job
    match: Optional[MatchResult] = None
    cover_letter: Optional[CoverLetter] = None

class PipelineResult(BaseModel):
    total_jobs_scraped: int
    total_jobs_matched: int
    results: list[JobWithScore]
    completed_at: datetime = Field(default_factory=datetime.now)