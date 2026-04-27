import logging
from fastapi import APIRouter, HTTPException, Query, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional
from backend.core.schemas import Job
from backend.utils.cache import job_cache
from backend.scraper.remoteok_scraper import RemoteOKScraper
from backend.scraper.hn_scraper import HNScraper
from backend.scraper.adzuna_scraper import AdzunaScraper
import asyncio

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/jobs", tags=["Jobs"])


# ── Request / Response Models ──────────────────────────────────────────────────

class ScrapeRequest(BaseModel):
    keywords: list[str]
    sources: list[str] = ["remoteok", "hn", "adzuna"]   # which scrapers to run
    use_cache: bool = True
    force_refresh: bool = False                           # bypass cache entirely


class ScrapeResponse(BaseModel):
    total: int
    sources: dict[str, int]                              # source → count
    jobs: list[Job]
    from_cache: bool


class CacheStatsResponse(BaseModel):
    total: int
    active: int
    expired: int
    max_size: int
    ttl_seconds: int


# ── Routes ─────────────────────────────────────────────────────────────────────

@router.get(
    "/",
    response_model=list[Job],
    summary="Get all cached jobs",
    description="Returns all non-expired jobs from the in-memory cache.",
)
async def get_jobs(
    source: Optional[str] = Query(None, description="Filter by source: remoteok | hn | adzuna"),
    min_score: Optional[float] = Query(None, ge=0.0, le=10.0, description="Minimum fit score filter"),
    search: Optional[str] = Query(None, description="Search in title, company, description"),
    limit: int = Query(50, ge=1, le=200, description="Max jobs to return"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
):
    """
    Retrieve cached jobs with optional filtering.

    Filters:
    - source: remoteok | hn | adzuna
    - search: full-text search across title, company, description
    - limit/offset: pagination
    """
    jobs = await job_cache.get_all()

    if not jobs:
        return []

    # Filter by source
    if source:
        source_lower = source.lower()
        jobs = [j for j in jobs if j.source == source_lower]

    # Full-text search
    if search:
        search_lower = search.lower()
        jobs = [
            j for j in jobs
            if search_lower in j.title.lower()
            or search_lower in j.company.lower()
            or search_lower in j.description.lower()
            or any(search_lower in tag.lower() for tag in j.tags)
        ]

    # Pagination
    total = len(jobs)
    paginated = jobs[offset: offset + limit]

    logger.info(f"[jobs] GET /jobs → {len(paginated)}/{total} jobs returned")
    return paginated


@router.get(
    "/{job_id}",
    response_model=Job,
    summary="Get a single job by ID",
)
async def get_job(job_id: str):
    """Retrieve a single job from cache by its ID."""
    job = await job_cache.get(job_id)
    if not job:
        raise HTTPException(
            status_code=404,
            detail=f"Job '{job_id}' not found in cache. It may have expired.",
        )
    return job


@router.post(
    "/scrape",
    response_model=ScrapeResponse,
    summary="Trigger job scraping",
    description="Scrape jobs from selected sources and store in cache.",
)
async def scrape_jobs(request: ScrapeRequest):
    """
    Trigger job scraping from one or more sources.

    - If use_cache=True and force_refresh=False, returns cached jobs if available
    - force_refresh=True clears cache before scraping
    - sources controls which scrapers to run
    """
    logger.info(
        f"[jobs] POST /scrape — keywords={request.keywords}, "
        f"sources={request.sources}, force_refresh={request.force_refresh}"
    )

    # Validate keywords
    if not request.keywords:
        raise HTTPException(
            status_code=422,
            detail="At least one keyword is required.",
        )

    # Check cache unless force refresh
    if request.use_cache and not request.force_refresh:
        cached = await job_cache.get_all()
        if cached:
            logger.info(f"[jobs] Returning {len(cached)} cached jobs")
            source_counts = _count_by_source(cached)
            return ScrapeResponse(
                total=len(cached),
                sources=source_counts,
                jobs=cached,
                from_cache=True,
            )

    # Clear cache on force refresh
    if request.force_refresh:
        await job_cache.clear()
        logger.info("[jobs] Cache cleared for force refresh")

    # Run selected scrapers
    scraper_map = {
        "remoteok": RemoteOKScraper,
        "hn":       HNScraper,
        "adzuna":   AdzunaScraper,
    }

    selected = [
        s.lower() for s in request.sources
        if s.lower() in scraper_map
    ]

    if not selected:
        raise HTTPException(
            status_code=422,
            detail=f"No valid sources provided. Valid options: {list(scraper_map.keys())}",
        )

    # Run scrapers concurrently
    tasks = [
        _run_scraper(scraper_map[source], request.keywords)
        for source in selected
    ]
    results = await asyncio.gather(*tasks)

    # Map source → jobs
    source_jobs: dict[str, list[Job]] = {
        source: jobs
        for source, jobs in zip(selected, results)
    }

    # Merge and deduplicate
    all_jobs: list[Job] = []
    seen_ids: set[str] = set()
    for jobs in source_jobs.values():
        for job in jobs:
            if job.id not in seen_ids:
                seen_ids.add(job.id)
                all_jobs.append(job)

    # Store in cache
    if all_jobs:
        await job_cache.set_many(all_jobs)
        await job_cache.save_to_disk()

    source_counts = {source: len(jobs) for source, jobs in source_jobs.items()}
    logger.info(f"[jobs] Scraped {len(all_jobs)} unique jobs: {source_counts}")

    return ScrapeResponse(
        total=len(all_jobs),
        sources=source_counts,
        jobs=all_jobs,
        from_cache=False,
    )


@router.delete(
    "/cache",
    summary="Clear job cache",
    description="Clears all cached jobs from memory.",
)
async def clear_cache():
    """Clear all jobs from the in-memory cache."""
    stats_before = await job_cache.stats()
    await job_cache.clear()
    logger.info(f"[jobs] Cache cleared — removed {stats_before['active']} jobs")
    return {
        "message": "Cache cleared successfully",
        "jobs_removed": stats_before["active"],
    }


@router.get(
    "/cache/stats",
    response_model=CacheStatsResponse,
    summary="Get cache statistics",
)
async def get_cache_stats():
    """Returns current cache statistics."""
    stats = await job_cache.stats()
    return CacheStatsResponse(**stats)


@router.get(
    "/sources/available",
    summary="Get available job sources",
)
async def get_available_sources():
    """Returns list of available job scraping sources."""
    return {
        "sources": [
            {
                "id": "remoteok",
                "name": "RemoteOK",
                "description": "Remote job listings via public JSON API",
                "auth_required": False,
            },
            {
                "id": "hn",
                "name": "Hacker News Who's Hiring",
                "description": "Monthly HN hiring thread via Algolia API",
                "auth_required": False,
            },
            {
                "id": "adzuna",
                "name": "Adzuna",
                "description": "Global job listings via REST API (free tier)",
                "auth_required": True,
                "env_vars": ["ADZUNA_APP_ID", "ADZUNA_APP_KEY"],
            },
        ]
    }


# ── Helpers ────────────────────────────────────────────────────────────────────

async def _run_scraper(scraper_class, keywords: list[str]) -> list[Job]:
    """Run a single scraper safely — returns [] on failure."""
    try:
        async with scraper_class() as scraper:
            return await scraper.scrape(keywords)
    except Exception as e:
        logger.error(f"[jobs] {scraper_class.__name__} failed: {e}")
        return []


def _count_by_source(jobs: list[Job]) -> dict[str, int]:
    """Count jobs grouped by source."""
    counts: dict[str, int] = {}
    for job in jobs:
        counts[job.source] = counts.get(job.source, 0) + 1
    return counts