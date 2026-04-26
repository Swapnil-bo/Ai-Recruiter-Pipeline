import asyncio
import logging
import hashlib
from abc import ABC, abstractmethod
from typing import Optional
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)
import httpx
from backend.core.schemas import Job
from backend.core.config import settings

logger = logging.getLogger(__name__)


# ── Base Scraper ───────────────────────────────────────────────────────────────

class BaseScraper(ABC):
    """
    Abstract base class for all job scrapers.
    All scrapers must implement `scrape()`.
    Provides:
    - Shared async HTTP client with retry logic
    - Job ID generation (deterministic hash)
    - Text cleaning utilities
    - Rate limiting via delay
    """

    source_name: str = "unknown"

    def __init__(
        self,
        max_jobs: int = settings.max_jobs_per_source,
        request_timeout: int = 30,
        rate_limit_delay: float = 1.0,
    ):
        self.max_jobs = max_jobs
        self.request_timeout = request_timeout
        self.rate_limit_delay = rate_limit_delay
        self._client: Optional[httpx.AsyncClient] = None

    # ── Lifecycle ──────────────────────────────────────────────────────────────

    async def __aenter__(self):
        self._client = httpx.AsyncClient(
            timeout=self.request_timeout,
            headers={"User-Agent": self._user_agent()},
            follow_redirects=True,
        )
        return self

    async def __aexit__(self, *args):
        if self._client:
            await self._client.aclose()

    # ── Abstract Interface ─────────────────────────────────────────────────────

    @abstractmethod
    async def scrape(self, keywords: list[str]) -> list[Job]:
        """
        Scrape jobs matching the given keywords.
        Must return a list of Job objects.
        Must respect self.max_jobs limit.
        """
        ...

    # ── Shared HTTP ────────────────────────────────────────────────────────────

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=8),
        retry=retry_if_exception_type((httpx.ConnectError, httpx.TimeoutException)),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
    async def _get(self, url: str, params: Optional[dict] = None) -> httpx.Response:
        """GET request with automatic retry on network errors."""
        if self._client is None:
            raise RuntimeError(
                f"{self.__class__.__name__} must be used as async context manager"
            )
        await asyncio.sleep(self.rate_limit_delay)
        response = await self._client.get(url, params=params)
        response.raise_for_status()
        return response

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=8),
        retry=retry_if_exception_type((httpx.ConnectError, httpx.TimeoutException)),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
    async def _get_json(self, url: str, params: Optional[dict] = None) -> dict | list:
        """GET request that returns parsed JSON."""
        response = await self._get(url, params=params)
        return response.json()

    # ── Utilities ──────────────────────────────────────────────────────────────

    @staticmethod
    def generate_job_id(source: str, unique_str: str) -> str:
        """
        Deterministic job ID from source + unique identifier.
        Same job scraped twice always gets the same ID → safe for caching.
        """
        raw = f"{source}::{unique_str}".encode("utf-8")
        return hashlib.md5(raw).hexdigest()

    @staticmethod
    def clean_text(text: str) -> str:
        """Normalize whitespace and strip HTML artifacts."""
        import re
        text = re.sub(r"<[^>]+>", " ", text)        # strip HTML tags
        text = re.sub(r"&[a-z]+;", " ", text)        # strip HTML entities
        text = re.sub(r"\s+", " ", text)             # collapse whitespace
        return text.strip()

    @staticmethod
    def truncate(text: str, max_chars: int = 3000) -> str:
        """Truncate description to avoid token overflow in LLM calls."""
        if len(text) <= max_chars:
            return text
        return text[:max_chars] + "..."

    @staticmethod
    def _user_agent() -> str:
        return (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        )

    # ── Logging ────────────────────────────────────────────────────────────────

    def log_scrape_result(self, jobs: list[Job]) -> None:
        logger.info(
            f"[{self.source_name}] Scraped {len(jobs)} jobs "
            f"(limit: {self.max_jobs})"
        )