import re
import logging
from datetime import datetime
from backend.core.schemas import Job
from backend.scraper.base_scraper import BaseScraper

logger = logging.getLogger(__name__)

HN_ALGOLIA_SEARCH = "https://hn.algolia.com/api/v1/search"
HN_ALGOLIA_ITEMS  = "https://hn.algolia.com/api/v1/items"


class HNScraper(BaseScraper):
    """
    Scrapes jobs from Hacker News 'Ask HN: Who's Hiring?' monthly thread.
    Uses HN Algolia API — no auth, no scraping, fully legal.
    Finds the latest hiring thread and parses top-level comments as job posts.
    """

    source_name = "hn"

    async def scrape(self, keywords: list[str]) -> list[Job]:
        logger.info(f"[hn] Scraping with keywords: {keywords}")

        thread_id = await self._get_latest_hiring_thread_id()
        if not thread_id:
            logger.error("[hn] Could not find latest Who's Hiring thread")
            return []

        logger.info(f"[hn] Found hiring thread: {thread_id}")
        comments = await self._get_thread_comments(thread_id)

        jobs: list[Job] = []
        keywords_lower = [kw.lower() for kw in keywords]

        for comment in comments:
            if len(jobs) >= self.max_jobs:
                break
            try:
                text = comment.get("text") or ""
                if not text:
                    continue

                # Keyword filter
                if keywords_lower and not any(kw in text.lower() for kw in keywords_lower):
                    continue

                job = self._parse_comment(comment)
                if job:
                    jobs.append(job)

            except Exception as e:
                logger.warning(f"[hn] Skipped comment {comment.get('id')}: {e}")
                continue

        self.log_scrape_result(jobs)
        return jobs

    # ── Thread Discovery ───────────────────────────────────────────────────────

    async def _get_latest_hiring_thread_id(self) -> str | None:
        """Find the most recent 'Ask HN: Who's Hiring?' thread via Algolia."""
        try:
            data = await self._get_json(
                HN_ALGOLIA_SEARCH,
                params={
                    "query": "Ask HN: Who is hiring?",
                    "tags": "story,ask_hn",
                    "hitsPerPage": 5,
                },
            )
            hits = data.get("hits", [])
            for hit in hits:
                title = hit.get("title", "").lower()
                if "who is hiring" in title or "who's hiring" in title:
                    return hit.get("objectID")
        except Exception as e:
            logger.error(f"[hn] Thread discovery failed: {e}")
        return None

    # ── Comment Fetching ───────────────────────────────────────────────────────

    async def _get_thread_comments(self, thread_id: str) -> list[dict]:
        """Fetch all top-level comments from the hiring thread."""
        try:
            data = await self._get_json(f"{HN_ALGOLIA_ITEMS}/{thread_id}")
            return data.get("children", [])
        except Exception as e:
            logger.error(f"[hn] Failed to fetch thread comments: {e}")
            return []

    # ── Comment Parsing ────────────────────────────────────────────────────────

    def _parse_comment(self, comment: dict) -> Job | None:
        """
        Parse a HN comment into a Job.
        HN job posts follow loose conventions:
        Line 1: Company | Role | Location | Remote/Onsite | Salary (optional)
        Rest: Description
        """
        raw_text = comment.get("text", "")
        if not raw_text:
            return None

        clean = self.clean_text(raw_text)
        if len(clean) < 50:                          # too short to be a real post
            return None

        lines = [l.strip() for l in clean.split(". ") if l.strip()]
        first_line = lines[0] if lines else clean[:120]

        # Extract title and company from first line
        title, company = self._extract_title_company(first_line)

        # Extract location
        location = self._extract_location(clean)

        # Extract salary
        salary = self._extract_salary(clean)

        # Build description — full text truncated
        description = self.truncate(clean)

        # Extract tags from known keywords
        tags = self._extract_tags(clean)

        # Posted date from comment timestamp
        created_at = comment.get("created_at")
        posted_at = None
        if created_at:
            try:
                posted_at = datetime.fromisoformat(
                    created_at.replace("Z", "+00:00")
                ).strftime("%Y-%m-%d")
            except Exception:
                pass

        comment_id = str(comment.get("id", ""))
        job_id = self.generate_job_id(self.source_name, comment_id)
        hn_url = f"https://news.ycombinator.com/item?id={comment_id}"

        return Job(
            id=job_id,
            title=title,
            company=company,
            location=location,
            description=description,
            url=hn_url,
            source=self.source_name,
            salary=salary,
            tags=tags,
            posted_at=posted_at,
        )

    # ── Extraction Helpers ─────────────────────────────────────────────────────

    def _extract_title_company(self, first_line: str) -> tuple[str, str]:
        """
        HN posts often start with: Company | Role | ...
        or: Role at Company
        """
        # Pattern: Company | Role
        if "|" in first_line:
            parts = [p.strip() for p in first_line.split("|")]
            company = parts[0] if parts[0] else "Unknown"
            title = parts[1] if len(parts) > 1 else "Software Engineer"
            return title[:100], company[:100]

        # Pattern: Role at Company
        match = re.search(r"^(.+?)\s+at\s+(.+?)[\.,|]", first_line, re.IGNORECASE)
        if match:
            return match.group(1).strip()[:100], match.group(2).strip()[:100]

        # Fallback
        return first_line[:80] or "Software Engineer", "Unknown"

    def _extract_location(self, text: str) -> str:
        """Extract location hints from job text."""
        text_lower = text.lower()
        if "remote" in text_lower:
            if "onsite" in text_lower or "on-site" in text_lower:
                return "Remote / Onsite"
            return "Remote"
        for pattern in [
            r"\b(san francisco|new york|london|berlin|bangalore|mumbai|delhi|toronto|singapore)\b"
        ]:
            match = re.search(pattern, text_lower)
            if match:
                return match.group(1).title()
        return "Location not specified"

    def _extract_salary(self, text: str) -> str | None:
        """Extract salary range if mentioned."""
        patterns = [
            r"\$[\d,]+\s*[-–]\s*\$[\d,]+",          # $100,000 - $150,000
            r"\$[\d,]+[kK]\s*[-–]\s*\$?[\d,]+[kK]", # $100k - $150k
            r"[\d,]+\s*[-–]\s*[\d,]+\s*USD",         # 100,000 - 150,000 USD
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(0).strip()
        return None

    def _extract_tags(self, text: str) -> list[str]:
        """Extract tech stack tags from free text."""
        known_tags = [
            "python", "javascript", "typescript", "react", "node", "golang",
            "rust", "java", "kotlin", "swift", "ml", "ai", "llm", "fastapi",
            "django", "aws", "gcp", "azure", "docker", "kubernetes", "remote",
            "fullstack", "backend", "frontend", "devops", "data", "mobile",
        ]
        text_lower = text.lower()
        return [tag for tag in known_tags if tag in text_lower][:10]