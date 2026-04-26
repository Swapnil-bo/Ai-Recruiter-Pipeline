import logging
from datetime import datetime
from backend.core.schemas import Job
from backend.scraper.base_scraper import BaseScraper

logger = logging.getLogger(__name__)

REMOTEOK_API_URL = "https://remoteok.com/api"


class RemoteOKScraper(BaseScraper):
    """
    Scrapes job listings from RemoteOK's public JSON API.
    No auth required. Returns up to max_jobs results.
    API docs: https://remoteok.com/api
    """

    source_name = "remoteok"

    async def scrape(self, keywords: list[str]) -> list[Job]:
        """
        Fetch all jobs from RemoteOK and filter by keywords client-side.
        RemoteOK API does not support query params for filtering.
        """
        logger.info(f"[remoteok] Scraping with keywords: {keywords}")

        try:
            raw: list = await self._get_json(REMOTEOK_API_URL)
        except Exception as e:
            logger.error(f"[remoteok] Failed to fetch API: {e}")
            return []

        # First item is a legal notice dict, not a job — skip it
        jobs_raw = [item for item in raw if isinstance(item, dict) and "id" in item]

        jobs: list[Job] = []
        keywords_lower = [kw.lower() for kw in keywords]

        for item in jobs_raw:
            if len(jobs) >= self.max_jobs:
                break
            try:
                searchable = " ".join([
                    item.get("position", ""),
                    item.get("company", ""),
                    " ".join(item.get("tags", [])),
                    item.get("description", ""),
                ]).lower()

                if keywords_lower and not any(kw in searchable for kw in keywords_lower):
                    continue

                job = self._parse_job(item)
                if job:
                    jobs.append(job)

            except Exception as e:
                logger.warning(f"[remoteok] Skipped job {item.get('id')}: {e}")
                continue

        self.log_scrape_result(jobs)
        return jobs

    def _parse_job(self, item: dict) -> Job | None:
        """Parse a raw RemoteOK API item into a Job schema."""
        job_id = self.generate_job_id(
            self.source_name,
            str(item.get("id", "")),
        )

        title = item.get("position", "").strip()
        company = item.get("company", "Unknown").strip()
        description = self.clean_text(item.get("description", ""))
        description = self.truncate(description)

        if not title or not description:
            return None

        # Salary — RemoteOK provides min/max separately
        salary = None
        salary_min = item.get("salary_min")
        salary_max = item.get("salary_max")
        if salary_min and salary_max:
            salary = f"${salary_min:,} - ${salary_max:,}"
        elif salary_min:
            salary = f"${salary_min:,}+"

        # Posted date
        posted_at = None
        epoch = item.get("epoch")
        if epoch:
            try:
                posted_at = datetime.utcfromtimestamp(epoch).strftime("%Y-%m-%d")
            except Exception:
                pass

        url = item.get("url") or f"https://remoteok.com/remote-jobs/{item.get('id')}"

        return Job(
            id=job_id,
            title=title,
            company=company,
            location="Remote",
            description=description,
            url=url,
            source=self.source_name,
            salary=salary,
            tags=item.get("tags", [])[:10],
            posted_at=posted_at,
        )