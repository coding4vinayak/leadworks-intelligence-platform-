"""Core enrichment engine - orchestrates data gathering from multiple sources."""
import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Set
import structlog

from backend.services.scrapers import (
    WebsiteScraper, LinkedInScraper, EmailFinder,
    TechStackScraper, SocialMediaScraper, ScraperResult,
)

logger = structlog.get_logger()


@dataclass
class EnrichmentResult:
    """Result of enriching a single lead."""
    success: bool
    lead_id: Optional[str] = None
    original_data: Dict[str, Any] = field(default_factory=dict)
    enriched_data: Dict[str, Any] = field(default_factory=dict)
    sources_used: List[str] = field(default_factory=list)
    fields_added: List[str] = field(default_factory=list)
    fields_updated: List[str] = field(default_factory=list)
    confidence_scores: Dict[str, str] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    duration_seconds: float = 0.0


class EnrichmentEngine:
    """
    Multi-source lead enrichment engine.

    Enrichment sources (in priority order):
    1. LinkedIn profile scraping
    2. Company website scraping
    3. Email discovery
    4. Tech stack detection
    5. Social media profiles
    6. AI-powered inference (OpenAI)
    7. WHOIS/DNS data

    Strategy: Uses available data points to find more data points.
    e.g., email domain -> company website -> tech stack + team members
    e.g., name + company -> LinkedIn -> full profile + job title
    """

    def __init__(self, proxies: Optional[List[str]] = None):
        self.proxies = proxies or []

    async def enrich_lead(
        self,
        lead_data: Dict[str, Any],
        sources: Optional[List[str]] = None,
        skip_sources: Optional[List[str]] = None,
        force_refresh: bool = False,
    ) -> EnrichmentResult:
        """
        Enrich a single lead with all available data.

        Args:
            lead_data: Current lead data (email, name, company, etc.)
            sources: Specific sources to use (default: all applicable)
            skip_sources: Sources to skip
            force_refresh: Re-enrich even if already enriched
        """
        import time
        start = time.time()

        result = EnrichmentResult(
            success=True,
            original_data=lead_data.copy(),
            enriched_data=lead_data.copy(),
        )

        skip = set(skip_sources or [])
        available_sources = self._determine_sources(lead_data, sources)
        tasks = []

        # Run enrichment tasks based on available data
        if "linkedin" in available_sources and "linkedin" not in skip:
            tasks.append(("linkedin", self._enrich_from_linkedin(lead_data)))

        if "company_website" in available_sources and "company_website" not in skip:
            tasks.append(("company_website", self._enrich_from_website(lead_data)))

        if "email_finder" in available_sources and "email_finder" not in skip:
            tasks.append(("email_finder", self._enrich_email(lead_data)))

        if "tech_stack" in available_sources and "tech_stack" not in skip:
            tasks.append(("tech_stack", self._enrich_tech_stack(lead_data)))

        if "social" in available_sources and "social" not in skip:
            tasks.append(("social", self._enrich_social(lead_data)))

        # Run all enrichment tasks concurrently
        if tasks:
            task_names = [t[0] for t in tasks]
            task_coros = [t[1] for t in tasks]
            results = await asyncio.gather(*task_coros, return_exceptions=True)

            for name, task_result in zip(task_names, results):
                if isinstance(task_result, Exception):
                    result.errors.append(f"{name}: {str(task_result)}")
                    continue

                if task_result and isinstance(task_result, dict):
                    result.sources_used.append(name)
                    # Merge enriched data (don't overwrite existing values)
                    for key, value in task_result.items():
                        if value and (not result.enriched_data.get(key) or force_refresh):
                            if key not in lead_data or not lead_data[key]:
                                result.fields_added.append(key)
                            else:
                                result.fields_updated.append(key)
                            result.enriched_data[key] = value

        result.duration_seconds = time.time() - start
        return result

    async def enrich_batch(
        self,
        leads: List[Dict[str, Any]],
        max_concurrent: int = 3,
        sources: Optional[List[str]] = None,
    ) -> List[EnrichmentResult]:
        """Enrich multiple leads with concurrency control."""
        semaphore = asyncio.Semaphore(max_concurrent)

        async def enrich_with_limit(lead):
            async with semaphore:
                return await self.enrich_lead(lead, sources=sources)

        return await asyncio.gather(
            *[enrich_with_limit(lead) for lead in leads],
            return_exceptions=True,
        )

    def _determine_sources(
        self, lead_data: Dict, requested: Optional[List[str]]
    ) -> Set[str]:
        """Determine which enrichment sources are applicable."""
        if requested:
            return set(requested)

        sources = set()
        email = lead_data.get("email", "")
        name = lead_data.get("first_name", "") or lead_data.get("full_name", "")
        company = lead_data.get("company_name", "")
        linkedin = lead_data.get("linkedin_url", "")
        domain = ""

        if email and "@" in email:
            domain = email.split("@")[1]

        # LinkedIn: if we have a URL or enough info to search
        if linkedin or (name and company):
            sources.add("linkedin")

        # Company website: if we have domain or company name
        if domain or company:
            sources.add("company_website")

        # Email finder: if we have name + domain but no email
        if not email and name and (domain or company):
            sources.add("email_finder")

        # Tech stack: if we have a domain
        if domain or company:
            sources.add("tech_stack")

        # Social: if we have name or URLs
        if name or lead_data.get("twitter_url") or lead_data.get("github_url"):
            sources.add("social")

        return sources

    async def _enrich_from_linkedin(self, lead_data: Dict) -> Optional[Dict]:
        """Enrich lead from LinkedIn profile."""
        scraper = LinkedInScraper(proxies=self.proxies)
        enriched = {}

        try:
            linkedin_url = lead_data.get("linkedin_url")

            if linkedin_url:
                # Scrape the profile directly
                result = await scraper.run(mode="profile", profile_urls=[linkedin_url])
            else:
                # Search for the person
                name = f"{lead_data.get('first_name', '')} {lead_data.get('last_name', '')}".strip()
                company = lead_data.get("company_name", "")
                result = await scraper.run(
                    mode="search",
                    query=f"{name} {company}",
                    max_results=3,
                )

            if result.success and result.data:
                profile = result.data[0]
                enriched["linkedin_url"] = profile.get("linkedin_url", linkedin_url)
                enriched["job_title"] = profile.get("job_title") or profile.get("headline")
                enriched["company_name"] = profile.get("company_name")
                enriched["first_name"] = profile.get("first_name")
                enriched["last_name"] = profile.get("last_name")
                enriched["city"] = profile.get("location")
                enriched["avatar_url"] = profile.get("avatar_url")

                # Clean None values
                enriched = {k: v for k, v in enriched.items() if v}

        except Exception as e:
            logger.warning("linkedin_enrichment_failed", error=str(e))
            return None

        return enriched if enriched else None

    async def _enrich_from_website(self, lead_data: Dict) -> Optional[Dict]:
        """Enrich from company website."""
        domain = ""
        email = lead_data.get("email", "")
        if email and "@" in email:
            domain = email.split("@")[1]

        if not domain:
            return None

        scraper = WebsiteScraper(proxies=self.proxies)
        enriched = {}

        try:
            result = await scraper.run(
                url=f"https://{domain}",
                depth=1,
                max_pages=5,
            )

            if result.success and result.data:
                site_data = result.data[0]

                # Company info from website
                company_info = site_data.get("company_info", {})
                if company_info:
                    enriched["company_name"] = company_info.get("name")
                    enriched["website"] = f"https://{domain}"

                # Social links
                social = site_data.get("social_links", {})
                if social.get("linkedin"):
                    company_linkedin = [l for l in social["linkedin"] if "/company/" in l]
                    if company_linkedin:
                        enriched["company_linkedin"] = company_linkedin[0]
                if social.get("twitter"):
                    enriched["company_twitter"] = list(social["twitter"])[0]

                enriched = {k: v for k, v in enriched.items() if v}

        except Exception as e:
            logger.warning("website_enrichment_failed", error=str(e))
            return None

        return enriched if enriched else None

    async def _enrich_email(self, lead_data: Dict) -> Optional[Dict]:
        """Find email address for the lead."""
        first_name = lead_data.get("first_name", "")
        last_name = lead_data.get("last_name", "")
        domain = ""
        company = lead_data.get("company_name", "")

        email = lead_data.get("email", "")
        if email and "@" in email:
            domain = email.split("@")[1]

        if not first_name or not last_name:
            return None

        finder = EmailFinder(proxies=self.proxies)

        try:
            result = await finder.run(
                first_name=first_name,
                last_name=last_name,
                domain=domain,
                company_name=company,
                verify=True,
            )

            if result.success and result.data:
                # Get highest confidence email
                best = result.data[0]
                return {"email": best["email"]}

        except Exception as e:
            logger.warning("email_enrichment_failed", error=str(e))

        return None

    async def _enrich_tech_stack(self, lead_data: Dict) -> Optional[Dict]:
        """Detect company tech stack."""
        domain = ""
        email = lead_data.get("email", "")
        if email and "@" in email:
            domain = email.split("@")[1]

        if not domain:
            return None

        scraper = TechStackScraper(proxies=self.proxies)

        try:
            result = await scraper.run(domain=domain, deep_scan=False)

            if result.success and result.data:
                tech_data = result.data[0]
                return {
                    "tech_stack": list(tech_data.get("technologies", {}).keys()),
                    "tech_categorized": tech_data.get("categorized", {}),
                }

        except Exception as e:
            logger.warning("tech_stack_enrichment_failed", error=str(e))

        return None

    async def _enrich_social(self, lead_data: Dict) -> Optional[Dict]:
        """Enrich from social media profiles."""
        enriched = {}
        scraper = SocialMediaScraper(proxies=self.proxies)

        # GitHub
        github_url = lead_data.get("github_url")
        if github_url:
            try:
                result = await scraper.run(platform="github", profile_url=github_url)
                if result.success and result.data:
                    profile = result.data[0]
                    enriched["github_bio"] = profile.get("bio")
                    enriched["github_company"] = profile.get("company")
                    enriched["github_languages"] = profile.get("languages", [])
                    if not lead_data.get("website"):
                        enriched["website"] = profile.get("website")
                    if not lead_data.get("email") and profile.get("email"):
                        enriched["email"] = profile["email"]
            except:
                pass

        enriched = {k: v for k, v in enriched.items() if v}
        return enriched if enriched else None
