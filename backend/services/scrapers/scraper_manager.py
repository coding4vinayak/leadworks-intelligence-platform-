"""Scraper Manager - orchestrates scraping jobs, manages queues, handles results."""
import asyncio
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID
import structlog

from backend.services.scrapers.base import ScraperResult
from backend.services.scrapers.website_scraper import WebsiteScraper
from backend.services.scrapers.linkedin_scraper import LinkedInScraper
from backend.services.scrapers.google_maps_scraper import GoogleMapsScraper
from backend.services.scrapers.email_finder import EmailFinder
from backend.services.scrapers.tech_stack_scraper import TechStackScraper
from backend.services.scrapers.social_scraper import SocialMediaScraper

logger = structlog.get_logger()


SCRAPER_MAP = {
    "website": WebsiteScraper,
    "linkedin_profile": LinkedInScraper,
    "linkedin_company": LinkedInScraper,
    "linkedin_search": LinkedInScraper,
    "google_maps": GoogleMapsScraper,
    "email_finder": EmailFinder,
    "tech_stack": TechStackScraper,
    "social_media": SocialMediaScraper,
}



class ScraperManager:
    """
    Orchestrates all scraping operations:
    - Queues and prioritizes jobs
    - Manages concurrent scrapers
    - Converts results to leads
    - Handles failures and retries
    - Triggers enrichment after scraping
    """

    def __init__(self, max_concurrent: int = 5, proxies: Optional[List[str]] = None):
        self.max_concurrent = max_concurrent
        self.proxies = proxies or []
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.active_jobs: Dict[str, Any] = {}

    async def run_job(
        self,
        job_type: str,
        params: Dict[str, Any],
        team_id: Optional[UUID] = None,
        triggered_by: Optional[UUID] = None,
        priority: int = 5,
    ) -> ScraperResult:
        """
        Execute a scraping job.

        Args:
            job_type: Type of scrape (website, linkedin_search, google_maps, etc.)
            params: Parameters for the scraper
            team_id: Team that owns this job
            triggered_by: User or system that triggered this
            priority: 1-10, 1 = highest
        """
        scraper_class = SCRAPER_MAP.get(job_type)
        if not scraper_class:
            return ScraperResult(
                success=False,
                errors=[f"Unknown job type: {job_type}"],
            )

        async with self.semaphore:
            logger.info(
                "scrape_job_started",
                job_type=job_type,
                params=params,
            )

            scraper = scraper_class(proxies=self.proxies)

            # Route to correct scraper method based on job type
            if job_type == "linkedin_search":
                params["mode"] = "search"
            elif job_type == "linkedin_profile":
                params["mode"] = "profile"
            elif job_type == "linkedin_company":
                params["mode"] = "company"

            result = await scraper.run(**params)

            logger.info(
                "scrape_job_completed",
                job_type=job_type,
                success=result.success,
                records=result.records_found,
                duration=result.duration_seconds,
            )

            return result

    async def run_batch(
        self,
        jobs: List[Dict[str, Any]],
    ) -> List[ScraperResult]:
        """
        Run multiple scraping jobs concurrently.

        Args:
            jobs: List of {"job_type": "...", "params": {...}}
        """
        tasks = [
            self.run_job(
                job_type=job["job_type"],
                params=job.get("params", {}),
                team_id=job.get("team_id"),
                triggered_by=job.get("triggered_by"),
                priority=job.get("priority", 5),
            )
            for job in jobs
        ]
        return await asyncio.gather(*tasks, return_exceptions=True)

    async def find_leads(
        self,
        query: str,
        sources: Optional[List[str]] = None,
        location: Optional[str] = None,
        max_per_source: int = 25,
    ) -> Dict[str, ScraperResult]:
        """
        High-level method: Find leads from multiple sources at once.

        Args:
            query: What to search for (e.g., "SaaS CTO", "marketing agencies")
            sources: Which sources to use (default: all)
            location: Location filter
            max_per_source: Max results per source
        """
        if sources is None:
            sources = ["linkedin", "google_maps", "website"]

        results: Dict[str, ScraperResult] = {}
        jobs = []

        if "linkedin" in sources:
            jobs.append({
                "job_type": "linkedin_search",
                "params": {
                    "query": query,
                    "location": location,
                    "max_results": max_per_source,
                },
            })

        if "google_maps" in sources:
            jobs.append({
                "job_type": "google_maps",
                "params": {
                    "query": query,
                    "location": location,
                    "max_results": max_per_source,
                },
            })

        batch_results = await self.run_batch(jobs)

        source_names = [s for s in sources if s in ("linkedin", "google_maps")]
        for name, result in zip(source_names, batch_results):
            if isinstance(result, Exception):
                results[name] = ScraperResult(
                    success=False, errors=[str(result)]
                )
            else:
                results[name] = result

        return results

    def results_to_leads(self, result: ScraperResult, source: str) -> List[Dict]:
        """
        Convert scraper results to lead-ready data format.

        Returns list of dicts ready to be inserted as Lead model instances.
        """
        leads = []

        for item in result.data:
            lead = {
                "source": source,
                "source_detail": result.source,
                "raw_data": item,
            }

            # Map common fields
            if "email" in item:
                lead["email"] = item["email"]
            if "first_name" in item:
                lead["first_name"] = item["first_name"]
            if "last_name" in item:
                lead["last_name"] = item["last_name"]
            if "full_name" in item:
                parts = item["full_name"].split(" ", 1)
                lead["first_name"] = lead.get("first_name") or parts[0]
                lead["last_name"] = lead.get("last_name") or (parts[1] if len(parts) > 1 else "")
            if "job_title" in item:
                lead["job_title"] = item["job_title"]
            if "company_name" in item:
                lead["company_name"] = item["company_name"]
            if "company" in item:
                lead["company_name"] = lead.get("company_name") or item["company"]
            if "linkedin_url" in item:
                lead["linkedin_url"] = item["linkedin_url"]
            if "phone" in item:
                lead["phone"] = item["phone"]
            if "website" in item:
                lead["website"] = item["website"]
            if "location" in item:
                lead["city"] = item["location"]
            if "name" in item and not lead.get("first_name"):
                # Business from Google Maps
                lead["company_name"] = item["name"]
            if "address" in item:
                lead["custom_fields"] = {"address": item["address"]}

            leads.append(lead)

        return leads
