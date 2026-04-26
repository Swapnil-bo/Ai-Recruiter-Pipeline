import json
import time
import asyncio
import logging
import aiofiles
from typing import Optional
from backend.core.config import settings
from backend.core.schemas import Job

logger = logging.getLogger(__name__)


# ── In-Memory Job Cache ────────────────────────────────────────────────────────

class JobCache:
    """
    Thread-safe async in-memory cache for scraped jobs.
    - TTL-based expiry per entry
    - Max size enforcement (evicts oldest 10% on overflow)
    - Persists to / loads from data/cached_jobs.json
    """

    def __init__(
        self,
        ttl: int = settings.cache_ttl_seconds,
        max_size: int = settings.max_cached_jobs,
        persist_path: str = "data/cached_jobs.json",
    ):
        self.ttl = ttl
        self.max_size = max_size
        self.persist_path = persist_path
        self._store: dict[str, dict] = {}   # job_id -> {data, expires_at}
        self._lock = asyncio.Lock()

    # ── Core Operations ────────────────────────────────────────────────────────

    async def set(self, job: Job) -> None:
        """Cache a single job."""
        async with self._lock:
            if len(self._store) >= self.max_size:
                self._evict_oldest()
            self._store[job.id] = {
                "data": job.model_dump(mode="json"),
                "expires_at": time.time() + self.ttl,
            }

    async def get(self, job_id: str) -> Optional[Job]:
        """Get a job by ID. Returns None if missing or expired."""
        async with self._lock:
            entry = self._store.get(job_id)
            if not entry:
                return None
            if time.time() > entry["expires_at"]:
                del self._store[job_id]
                return None
            return Job(**entry["data"])

    async def set_many(self, jobs: list[Job]) -> None:
        """Bulk cache a list of jobs under a single lock acquisition."""
        async with self._lock:
            for job in jobs:
                if len(self._store) >= self.max_size:
                    self._evict_oldest()
                self._store[job.id] = {
                    "data": job.model_dump(mode="json"),
                    "expires_at": time.time() + self.ttl,
                }
        logger.info(f"Cached {len(jobs)} jobs. Total: {len(self._store)}")

    async def get_all(self) -> list[Job]:
        """Return all non-expired cached jobs."""
        async with self._lock:
            now = time.time()
            valid = []
            expired_keys = []

            for job_id, entry in self._store.items():
                if now > entry["expires_at"]:
                    expired_keys.append(job_id)
                else:
                    valid.append(Job(**entry["data"]))

            for key in expired_keys:
                del self._store[key]

            if expired_keys:
                logger.debug(f"Evicted {len(expired_keys)} expired jobs during get_all")

            return valid

    async def delete(self, job_id: str) -> None:
        async with self._lock:
            self._store.pop(job_id, None)

    async def clear(self) -> None:
        async with self._lock:
            self._store.clear()
        logger.info("Job cache cleared")

    # ── Stats ──────────────────────────────────────────────────────────────────

    async def stats(self) -> dict:
        async with self._lock:
            now = time.time()
            total = len(self._store)
            expired = sum(
                1 for e in self._store.values() if now > e["expires_at"]
            )
            return {
                "total": total,
                "active": total - expired,
                "expired": expired,
                "max_size": self.max_size,
                "ttl_seconds": self.ttl,
            }

    # ── Persistence ────────────────────────────────────────────────────────────

    async def save_to_disk(self) -> None:
        """Persist active cache to disk using non-blocking async I/O."""
        async with self._lock:
            now = time.time()
            active = {
                job_id: entry
                for job_id, entry in self._store.items()
                if now <= entry["expires_at"]
            }

        try:
            async with aiofiles.open(self.persist_path, "w", encoding="utf-8") as f:
                await f.write(json.dumps(active, indent=2, default=str))
            logger.info(f"Persisted {len(active)} jobs to {self.persist_path}")
        except Exception as e:
            logger.error(f"Failed to persist cache: {e}")

    async def load_from_disk(self) -> None:
        """Load cache from disk on startup using non-blocking async I/O."""
        try:
            async with aiofiles.open(self.persist_path, "r", encoding="utf-8") as f:
                content = await f.read()
            raw = json.loads(content)

            now = time.time()
            loaded = 0
            async with self._lock:
                for job_id, entry in raw.items():
                    if now <= entry["expires_at"]:
                        self._store[job_id] = entry
                        loaded += 1

            logger.info(f"Loaded {loaded} valid jobs from disk cache")
        except FileNotFoundError:
            logger.info("No disk cache found, starting fresh")
        except Exception as e:
            logger.error(f"Failed to load cache from disk: {e}")

    # ── Private ────────────────────────────────────────────────────────────────

    def _evict_oldest(self) -> None:
        """Remove oldest 10% of entries. Must be called within a locked context."""
        evict_count = max(1, self.max_size // 10)
        sorted_keys = sorted(
            self._store.keys(),
            key=lambda k: self._store[k]["expires_at"],
        )
        for key in sorted_keys[:evict_count]:
            del self._store[key]
        logger.debug(f"Evicted {evict_count} oldest jobs from cache")


# ── Singleton ──────────────────────────────────────────────────────────────────

job_cache = JobCache()