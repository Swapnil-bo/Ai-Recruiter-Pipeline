import logging
from datetime import datetime
from backend.core.schemas import Job
from backend.core.config import settings
from backend.scraper.base_scraper import BaseScraper

logger = logging.getLogger(__name__)

ADZUNA_API_URL = "https://api.adzuna.com/v1/api/jobs"


class AdzunaScraper(BaseScraper):
    """
    Scrapes job listings from Adzuna's REST API.
    Free tier: 250 requests/month. Supports India (in) and global.
    API docs: https://developer.adzuna.com/docs/search
    """

    source_name = "adzuna"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.app_id = settings.adzuna_app_id
        self.app_key = settings.adzuna_app_key
        self.country = settings.adzuna_country

    async def scrape(self, keywords: list[str]) -> list[Job]:
        logger.info(f"[adzuna] Scraping with keywords: {keywords}")

        if not self.app_id or not self.app_key:
            logger.warning("[adzuna] No API credentials found — skipping")
            return []

        if not keywords:
            logger.warning("[adzuna] No keywords provided — skipping")
            return []

        query = " ".join(keywords)
        jobs: list[Job] = []
        page = 1
        results_per_page = min(self.max_jobs, 50)   # Adzuna max is 50 per page

        while len(jobs) < self.max_jobs:
            try:
                data = await self._get_json(
                    f"{ADZUNA_API_URL}/{self.country}/search/{page}",
                    params={
                        "app_id": self.app_id,
                        "app_key": self.app_key,
                        "what": query,
                        "results_per_page": results_per_page,
                        "content-type": "application/json",
                        "sort_by": "date",              # freshest first
                    },
                )
            except Exception as e:
                logger.error(f"[adzuna] API request failed (page {page}): {e}")
                break

            results = data.get("results", [])
            if not results:
                logger.info(f"[adzuna] No more results at page {page}")
                break

            for item in results:
                if len(jobs) >= self.max_jobs:
                    break
                try:
                    job = self._parse_job(item)
                    if job:
                        jobs.append(job)
                except Exception as e:
                    logger.warning(f"[adzuna] Skipped job {item.get('id')}: {e}")
                    continue

            # If fewer results than requested — no more pages
            if len(results) < results_per_page:
                break

            page += 1

        self.log_scrape_result(jobs)
        return jobs

    # ── Job Parsing ────────────────────────────────────────────────────────────

    def _parse_job(self, item: dict) -> Job | None:
        """Parse a raw Adzuna API result into a Job schema."""
        raw_id = item.get("id", "")
        if not raw_id:
            return None

        job_id = self.generate_job_id(self.source_name, str(raw_id))

        title = item.get("title", "").strip()
        if not title:
            return None

        # Company
        company = (
            item.get("company", {}).get("display_name", "Unknown").strip()
        )

        # Location
        location_data = item.get("location", {})
        location_parts = location_data.get("area", [])
        location = (
            ", ".join(location_parts[-2:]) if location_parts
            else location_data.get("display_name", "Not specified")
        )

        # Description
        description = self.clean_text(item.get("description", ""))
        description = self.truncate(description)
        if not description:
            return None

        # Salary
        salary = self._parse_salary(item)

        # Category tags
        category = item.get("category", {}).get("label", "")
        tags = [t.strip().lower() for t in category.split("/")] if category else []

        # Posted date
        posted_at = None
        created = item.get("created")
        if created:
            try:
                posted_at = datetime.fromisoformat(
                    created.replace("Z", "+00:00")
                ).strftime("%Y-%m-%d")
            except Exception:
                pass

        return Job(
            id=job_id,
            title=title,
            company=company,
            location=location,
            description=description,
            url=item.get("redirect_url", ""),
            source=self.source_name,
            salary=salary,
            tags=tags[:10],
            posted_at=posted_at,
        )

    def _parse_salary(self, item: dict) -> str | None:
        """Build salary string from Adzuna min/max fields."""
        salary_min = item.get("salary_min")
        salary_max = item.get("salary_max")

        if salary_min and salary_max:
            return f"${int(salary_min):,} - ${int(salary_max):,}"
        elif salary_min:
            return f"${int(salary_min):,}+"
        elif salary_max:
            return f"Up to ${int(salary_max):,}"
        return None