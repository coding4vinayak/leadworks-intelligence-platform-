"""Social media scraper - extracts profile data from various platforms."""
import re
from typing import Dict, List, Optional
from bs4 import BeautifulSoup
import structlog

from backend.services.scrapers.base import BaseScraper, ScraperResult

logger = structlog.get_logger()


class SocialMediaScraper(BaseScraper):
    """
    Scrapes public social media profiles for lead enrichment.
    Supports: Twitter/X, GitHub, Crunchbase (public pages).
    """

    async def scrape(
        self,
        platform: str,
        profile_url: Optional[str] = None,
        username: Optional[str] = None,
        search_query: Optional[str] = None,
    ) -> ScraperResult:
        """
        Scrape social media profiles.

        Args:
            platform: "twitter", "github", "crunchbase"
            profile_url: Direct URL to profile
            username: Username to look up
            search_query: Search term for finding profiles
        """
        if platform == "twitter":
            return await self._scrape_twitter(profile_url, username)
        elif platform == "github":
            return await self._scrape_github(profile_url, username)
        elif platform == "crunchbase":
            return await self._scrape_crunchbase(profile_url, search_query)
        else:
            return ScraperResult(success=False, errors=[f"Unsupported: {platform}"])

    async def _scrape_twitter(
        self, url: Optional[str], username: Optional[str]
    ) -> ScraperResult:
        """Scrape Twitter/X profile for public info via Google cache/nitter."""
        profile = {}

        if username and not url:
            url = f"https://twitter.com/{username}"

        if not url:
            return ScraperResult(success=False, errors=["No URL or username"])

        # Use Google to find cached profile info
        try:
            search_url = "https://www.google.com/search"
            handle = url.split("/")[-1]
            response = await self.fetch(
                search_url,
                params={"q": f"site:twitter.com {handle}"},
            )
            soup = BeautifulSoup(response.text, 'lxml')

            profile["twitter_url"] = url
            profile["username"] = handle

            # Try to get bio from search snippet
            snippets = soup.find_all("span", class_=re.compile(r'aCOpRe|st'))
            for snippet in snippets:
                text = snippet.get_text(strip=True)
                if len(text) > 20:
                    profile["bio"] = text[:300]
                    break

        except Exception as e:
            logger.warning("twitter_scrape_failed", error=str(e))

        return ScraperResult(
            success=bool(profile),
            data=[profile] if profile else [],
            records_found=1 if profile else 0,
            metadata={"platform": "twitter"},
        )

    async def _scrape_github(
        self, url: Optional[str], username: Optional[str]
    ) -> ScraperResult:
        """Scrape GitHub profile - great for developer leads."""
        profile = {}

        if username and not url:
            url = f"https://github.com/{username}"

        if not url:
            return ScraperResult(success=False, errors=["No URL or username"])

        try:
            response = await self.fetch(url)
            soup = BeautifulSoup(response.text, 'lxml')

            profile["github_url"] = url
            profile["username"] = url.rstrip("/").split("/")[-1]

            # Full name
            name_tag = soup.find("span", class_="p-name")
            if name_tag:
                profile["full_name"] = name_tag.get_text(strip=True)

            # Bio
            bio_tag = soup.find("div", class_="p-note")
            if bio_tag:
                profile["bio"] = bio_tag.get_text(strip=True)

            # Company
            org_tag = soup.find("span", class_="p-org")
            if org_tag:
                profile["company"] = org_tag.get_text(strip=True)

            # Location
            loc_tag = soup.find("span", class_="p-label")
            if loc_tag:
                profile["location"] = loc_tag.get_text(strip=True)

            # Website
            blog_tag = soup.find("a", class_=re.compile(r'Link--primary'))
            if blog_tag and blog_tag.get("href", "").startswith("http"):
                profile["website"] = blog_tag["href"]

            # Email (if public)
            email_link = soup.find("a", href=re.compile(r'^mailto:'))
            if email_link:
                profile["email"] = email_link["href"].replace("mailto:", "")

            # Followers/repos count
            counters = soup.find_all("span", class_="Counter")
            if len(counters) >= 2:
                try:
                    profile["repos"] = int(counters[0].get_text(strip=True).replace(",", ""))
                except:
                    pass

            # Pinned repos (shows expertise)
            pinned = soup.find_all("span", class_="repo")
            profile["pinned_repos"] = [r.get_text(strip=True) for r in pinned[:6]]

            # Languages (from contribution activity)
            langs = soup.find_all("span", class_="color-fg-default")
            profile["languages"] = list(set(
                l.get_text(strip=True) for l in langs
                if l.get_text(strip=True) in [
                    "Python", "JavaScript", "TypeScript", "Go", "Rust",
                    "Java", "Ruby", "C++", "C#", "PHP", "Swift", "Kotlin"
                ]
            ))

        except Exception as e:
            logger.warning("github_scrape_failed", url=url, error=str(e))

        return ScraperResult(
            success=bool(profile.get("full_name") or profile.get("username")),
            data=[profile] if profile else [],
            records_found=1 if profile else 0,
            metadata={"platform": "github"},
        )

    async def _scrape_crunchbase(
        self, url: Optional[str], search_query: Optional[str]
    ) -> ScraperResult:
        """Scrape Crunchbase for company data (funding, employees, etc.)."""
        company_data = {}

        if search_query and not url:
            # Find company on Crunchbase via Google
            try:
                response = await self.fetch(
                    "https://www.google.com/search",
                    params={"q": f"site:crunchbase.com {search_query}"},
                )
                soup = BeautifulSoup(response.text, 'lxml')
                for a in soup.find_all("a", href=True):
                    if "crunchbase.com/organization/" in a["href"]:
                        url = a["href"].split("&")[0]
                        if "/url?q=" in url:
                            url = url.split("/url?q=")[1]
                        break
            except:
                pass

        if not url:
            return ScraperResult(success=False, errors=["Company not found"])

        try:
            response = await self.fetch(url)
            soup = BeautifulSoup(response.text, 'lxml')

            company_data["crunchbase_url"] = url

            # Company name
            title = soup.find("title")
            if title:
                company_data["name"] = title.get_text(strip=True).split("-")[0].strip()

            # Description from meta
            desc = soup.find("meta", attrs={"name": "description"})
            if desc:
                company_data["description"] = desc.get("content", "")[:500]

        except Exception as e:
            logger.warning("crunchbase_scrape_failed", error=str(e))

        return ScraperResult(
            success=bool(company_data),
            data=[company_data] if company_data else [],
            records_found=1 if company_data else 0,
            metadata={"platform": "crunchbase"},
        )
