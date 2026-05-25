"""LinkedIn scraper - extracts profiles, companies, and search results."""
import re
import json
from typing import Dict, List, Optional
from urllib.parse import quote_plus
from bs4 import BeautifulSoup
import structlog

from backend.services.scrapers.base import BaseScraper, ScraperResult

logger = structlog.get_logger()


class LinkedInScraper(BaseScraper):
    """
    Scrapes LinkedIn for lead data using multiple strategies:
    1. Public profile scraping (no auth needed for basic info)
    2. Google dorking for LinkedIn profiles
    3. LinkedIn search result parsing
    4. Company page employee lists

    Note: For production, consider using LinkedIn's official API or
    services like Proxycurl/PhantomBuster for better reliability.
    """

    GOOGLE_SEARCH_URL = "https://www.google.com/search"
    LINKEDIN_BASE = "https://www.linkedin.com"

    async def scrape(
        self,
        mode: str = "search",
        query: Optional[str] = None,
        profile_urls: Optional[List[str]] = None,
        company_url: Optional[str] = None,
        location: Optional[str] = None,
        job_title: Optional[str] = None,
        industry: Optional[str] = None,
        max_results: int = 25,
    ) -> ScraperResult:
        """
        Scrape LinkedIn data.

        Modes:
        - "search": Find profiles by keywords/title/location via Google
        - "profile": Scrape specific profile URLs
        - "company": Get employees from a company page
        """
        if mode == "search":
            return await self._search_profiles(
                query=query, location=location,
                job_title=job_title, industry=industry,
                max_results=max_results,
            )
        elif mode == "profile":
            return await self._scrape_profiles(profile_urls or [])
        elif mode == "company":
            return await self._scrape_company(company_url or "")
        else:
            return ScraperResult(success=False, errors=[f"Unknown mode: {mode}"])

    async def _search_profiles(
        self,
        query: Optional[str] = None,
        location: Optional[str] = None,
        job_title: Optional[str] = None,
        industry: Optional[str] = None,
        max_results: int = 25,
    ) -> ScraperResult:
        """Search for LinkedIn profiles using Google dorking."""
        # Build Google dork query
        search_parts = ['site:linkedin.com/in/']

        if query:
            search_parts.append(query)
        if job_title:
            search_parts.append(f'"{job_title}"')
        if location:
            search_parts.append(f'"{location}"')
        if industry:
            search_parts.append(f'"{industry}"')

        search_query = " ".join(search_parts)
        profiles: List[Dict] = []
        page = 0

        while len(profiles) < max_results:
            params = {
                "q": search_query,
                "start": page * 10,
                "num": 10,
            }

            try:
                response = await self.fetch(self.GOOGLE_SEARCH_URL, params=params)
                soup = BeautifulSoup(response.text, 'lxml')

                results = soup.find_all("div", class_="g")
                if not results:
                    break

                for result in results:
                    link_tag = result.find("a")
                    if not link_tag:
                        continue

                    href = link_tag.get("href", "")
                    if "linkedin.com/in/" not in href:
                        continue

                    profile = self._parse_google_result(result, href)
                    if profile:
                        profiles.append(profile)

                    if len(profiles) >= max_results:
                        break

                page += 1
                if page > 5:  # Safety limit
                    break

            except Exception as e:
                logger.warning("linkedin_search_page_failed", page=page, error=str(e))
                break

        return ScraperResult(
            success=True,
            data=profiles,
            records_found=len(profiles),
            metadata={"query": search_query, "mode": "search"},
        )

    def _parse_google_result(self, result, href: str) -> Optional[Dict]:
        """Parse a Google search result for LinkedIn profile info."""
        profile = {"linkedin_url": href.split("&")[0]}

        # Title usually has: "Name - Title - Company | LinkedIn"
        title_tag = result.find("h3")
        if title_tag:
            title_text = title_tag.get_text(strip=True)
            # Remove " | LinkedIn" suffix
            title_text = re.sub(r'\s*[\|–-]\s*LinkedIn\s*$', '', title_text)

            parts = [p.strip() for p in re.split(r'\s*[-–|]\s*', title_text)]
            if parts:
                profile["full_name"] = parts[0]
                # Try to split first/last name
                name_parts = parts[0].split(" ", 1)
                profile["first_name"] = name_parts[0]
                profile["last_name"] = name_parts[1] if len(name_parts) > 1 else ""

            if len(parts) >= 2:
                profile["job_title"] = parts[1]
            if len(parts) >= 3:
                profile["company_name"] = parts[2]

        # Snippet might have location/description
        snippet_tag = result.find("div", class_=re.compile(r'VwiC3b|IsZvec'))
        if snippet_tag:
            snippet = snippet_tag.get_text(strip=True)
            profile["description"] = snippet[:300]

            # Try to extract location
            loc_match = re.search(r'(\w[\w\s]+,\s*\w[\w\s]+(?:Area)?)', snippet)
            if loc_match:
                profile["location"] = loc_match.group(1).strip()

        return profile if profile.get("full_name") else None

    async def _scrape_profiles(self, profile_urls: List[str]) -> ScraperResult:
        """Scrape individual LinkedIn profile pages for public info."""
        profiles: List[Dict] = []

        for url in profile_urls:
            try:
                response = await self.fetch(url)
                profile = self._parse_profile_page(response.text, url)
                if profile:
                    profiles.append(profile)
            except Exception as e:
                logger.warning("profile_scrape_failed", url=url, error=str(e))

        return ScraperResult(
            success=True,
            data=profiles,
            records_found=len(profiles),
            metadata={"mode": "profile", "urls_attempted": len(profile_urls)},
        )

    def _parse_profile_page(self, html: str, url: str) -> Optional[Dict]:
        """Parse LinkedIn profile page HTML."""
        soup = BeautifulSoup(html, 'lxml')
        profile = {"linkedin_url": url}

        # Name from title or h1
        title = soup.find("title")
        if title:
            name = title.get_text(strip=True).split("|")[0].split("-")[0].strip()
            profile["full_name"] = name
            name_parts = name.split(" ", 1)
            profile["first_name"] = name_parts[0]
            profile["last_name"] = name_parts[1] if len(name_parts) > 1 else ""

        # Meta description often has headline
        meta_desc = soup.find("meta", attrs={"name": "description"})
        if meta_desc:
            desc = meta_desc.get("content", "")
            profile["headline"] = desc[:200]

        # Try to find structured data
        scripts = soup.find_all("script", {"type": "application/ld+json"})
        for script in scripts:
            try:
                data = json.loads(script.string)
                if isinstance(data, dict) and data.get("@type") == "Person":
                    profile["full_name"] = profile.get("full_name") or data.get("name")
                    profile["job_title"] = data.get("jobTitle")
                    profile["company_name"] = data.get("worksFor", {}).get("name")
                    profile["location"] = data.get("address", {}).get("addressLocality")
                    profile["description"] = data.get("description")
            except:
                pass

        # Open Graph image (profile photo)
        og_image = soup.find("meta", attrs={"property": "og:image"})
        if og_image:
            profile["avatar_url"] = og_image.get("content")

        return profile if profile.get("full_name") else None

    async def _scrape_company(self, company_url: str) -> ScraperResult:
        """Scrape a LinkedIn company page for employee data."""
        profiles: List[Dict] = []

        try:
            response = await self.fetch(company_url)
            soup = BeautifulSoup(response.text, 'lxml')

            company_info = {"linkedin_url": company_url}

            # Company name
            title = soup.find("title")
            if title:
                company_info["name"] = title.get_text(strip=True).split("|")[0].strip()

            # Try to get employees via Google dorking
            company_name = company_info.get("name", "")
            if company_name:
                search_result = await self._search_profiles(
                    query=f'"{company_name}"',
                    max_results=25,
                )
                profiles = search_result.data
                for p in profiles:
                    p["company_name"] = company_name

        except Exception as e:
            logger.error("company_scrape_failed", url=company_url, error=str(e))

        return ScraperResult(
            success=True,
            data=profiles,
            records_found=len(profiles),
            metadata={"mode": "company", "company_url": company_url},
        )
