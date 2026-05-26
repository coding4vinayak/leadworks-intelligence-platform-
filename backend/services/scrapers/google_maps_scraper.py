"""Google Maps scraper - finds businesses with contact info for local lead gen."""
import re
import json
from typing import Dict, List, Optional
from urllib.parse import quote_plus
from bs4 import BeautifulSoup
import structlog

from backend.services.scrapers.base import BaseScraper, ScraperResult

logger = structlog.get_logger()


class GoogleMapsScraper(BaseScraper):
    """
    Scrapes Google Maps/Places for business listings.
    Extracts: business name, phone, website, address, rating, reviews, category.

    Great for local lead generation (e.g., "dentists in Chicago", "SaaS companies SF").
    """

    GOOGLE_MAPS_SEARCH = "https://www.google.com/maps/search/"
    GOOGLE_SEARCH_URL = "https://www.google.com/search"

    async def scrape(
        self,
        query: str,
        location: Optional[str] = None,
        max_results: int = 50,
        include_reviews: bool = False,
        min_rating: Optional[float] = None,
        business_type: Optional[str] = None,
    ) -> ScraperResult:
        """
        Scrape Google Maps for business listings.

        Args:
            query: Search query (e.g., "marketing agencies")
            location: Location to search in (e.g., "New York, NY")
            max_results: Maximum businesses to find
            include_reviews: Whether to fetch review count
            min_rating: Minimum star rating filter
            business_type: Additional type filter
        """
        search_query = query
        if location:
            search_query = f"{query} in {location}"

        businesses: List[Dict] = []

        # Strategy 1: Google search with map pack results
        businesses.extend(await self._search_google_maps(search_query, max_results))

        # Strategy 2: Direct Maps URL scraping
        if len(businesses) < max_results:
            more = await self._scrape_maps_url(search_query, max_results - len(businesses))
            businesses.extend(more)

        # Deduplicate by name + phone
        seen = set()
        unique_businesses = []
        for biz in businesses:
            key = (biz.get("name", "").lower(), biz.get("phone", ""))
            if key not in seen:
                seen.add(key)
                unique_businesses.append(biz)

        # Filter by rating
        if min_rating:
            unique_businesses = [
                b for b in unique_businesses
                if (b.get("rating") or 0) >= min_rating
            ]

        # Enrich with website data if we have URLs
        for biz in unique_businesses[:max_results]:
            biz["source"] = "google_maps"
            biz["search_query"] = search_query

        return ScraperResult(
            success=True,
            data=unique_businesses[:max_results],
            records_found=len(unique_businesses[:max_results]),
            metadata={"query": search_query, "location": location},
        )

    async def _search_google_maps(self, query: str, max_results: int) -> List[Dict]:
        """Use Google search to find local pack / Maps results."""
        businesses = []

        params = {
            "q": query,
            "num": 20,
            "tbm": "lcl",  # Local results
        }

        try:
            response = await self.fetch(self.GOOGLE_SEARCH_URL, params=params)
            soup = BeautifulSoup(response.text, 'lxml')

            # Parse local pack results
            local_results = soup.find_all("div", class_=re.compile(r'VkpGBb|rllt__details'))
            for result in local_results[:max_results]:
                biz = self._parse_local_result(result)
                if biz:
                    businesses.append(biz)

            # Also try the standard search with map intent
            if not businesses:
                params["tbm"] = ""
                params["q"] = f"{query} phone address"
                response = await self.fetch(self.GOOGLE_SEARCH_URL, params=params)
                soup = BeautifulSoup(response.text, 'lxml')

                # Parse knowledge panel and local pack
                businesses.extend(self._parse_search_businesses(soup))

        except Exception as e:
            logger.warning("google_maps_search_failed", error=str(e))

        return businesses

    async def _scrape_maps_url(self, query: str, max_results: int) -> List[Dict]:
        """Direct scraping of Google Maps search results page."""
        businesses = []

        encoded_query = quote_plus(query)
        url = f"{self.GOOGLE_MAPS_SEARCH}{encoded_query}"

        try:
            response = await self.fetch(url)

            # Google Maps returns data in a complex JS format
            # Try to extract business data from the page source
            businesses = self._parse_maps_page(response.text, max_results)

        except Exception as e:
            logger.warning("maps_url_scrape_failed", error=str(e))

        return businesses

    def _parse_local_result(self, result) -> Optional[Dict]:
        """Parse a Google local pack result."""
        biz = {}

        # Business name
        name_tag = result.find(["span", "div"], class_=re.compile(r'OSrXXb|dbg0pd'))
        if name_tag:
            biz["name"] = name_tag.get_text(strip=True)

        # Rating
        rating_tag = result.find("span", class_=re.compile(r'yi40Hd|Fam1ne'))
        if rating_tag:
            try:
                biz["rating"] = float(rating_tag.get_text(strip=True))
            except:
                pass

        # Review count
        reviews_tag = result.find("span", class_=re.compile(r'RDApEe|hqzQac'))
        if reviews_tag:
            review_text = reviews_tag.get_text(strip=True)
            nums = re.findall(r'\d+', review_text)
            if nums:
                biz["review_count"] = int(nums[0])

        # Address
        addr_tag = result.find("span", class_=re.compile(r'rllt__details|lqhpac'))
        if addr_tag:
            biz["address"] = addr_tag.get_text(strip=True)

        # Phone
        phone_spans = result.find_all("span")
        for span in phone_spans:
            text = span.get_text(strip=True)
            if re.match(r'^[\(\+]?\d[\d\s\-\(\)\.]{7,}$', text):
                biz["phone"] = text
                break

        # Category
        cat_tag = result.find("span", class_=re.compile(r'YhemCb'))
        if cat_tag:
            biz["category"] = cat_tag.get_text(strip=True)

        # Website link
        links = result.find_all("a", href=True)
        for link in links:
            href = link.get("href", "")
            if href.startswith("http") and "google" not in href:
                biz["website"] = href
                break

        return biz if biz.get("name") else None

    def _parse_search_businesses(self, soup: BeautifulSoup) -> List[Dict]:
        """Parse business info from standard Google search results."""
        businesses = []

        # Knowledge panel
        kp = soup.find("div", class_=re.compile(r'kp-wholepage'))
        if kp:
            biz = {}
            name = kp.find(["h2", "div"], class_=re.compile(r'qrShPb|SPZz6b'))
            if name:
                biz["name"] = name.get_text(strip=True)

            # Phone from knowledge panel
            phone_div = kp.find(text=re.compile(r'Phone'))
            if phone_div:
                parent = phone_div.parent
                if parent:
                    biz["phone"] = parent.get_text(strip=True).replace("Phone:", "").strip()

            if biz.get("name"):
                businesses.append(biz)

        return businesses

    def _parse_maps_page(self, html: str, max_results: int) -> List[Dict]:
        """
        Parse Google Maps page data.
        Maps embeds business data in the page source as JSON-like structures.
        """
        businesses = []

        # Try to find business data in embedded JSON
        # Google Maps includes data in script tags or inline JS
        patterns = [
            r'\["([^"]+)",null,null,null,null,null,null,\["([^"]*)"',  # name, address
            r'"([^"]{3,50})",\s*"(\+?\d[\d\s\-\(\)\.]{7,})"',  # name, phone
        ]

        # Extract what we can from the raw HTML
        soup = BeautifulSoup(html, 'lxml')

        # Look for aria-label attributes that often contain business names
        items = soup.find_all(attrs={"aria-label": re.compile(r'.{5,}')})
        for item in items[:max_results]:
            label = item.get("aria-label", "")
            if len(label) > 3 and len(label) < 100:
                biz = {"name": label}
                # Check for nested data
                href = item.get("href", "")
                if "place" in href:
                    biz["maps_url"] = href
                businesses.append(biz)

        return businesses[:max_results]
