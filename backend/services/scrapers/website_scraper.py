"""Website scraper - extracts contact info, emails, social links from any website."""
import re
from typing import Dict, List, Optional, Set
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
import structlog

from backend.services.scrapers.base import BaseScraper, ScraperResult

logger = structlog.get_logger()

# Regex patterns
EMAIL_PATTERN = re.compile(
    r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
)
PHONE_PATTERN = re.compile(
    r'[\+]?[(]?[0-9]{1,4}[)]?[-\s\./0-9]{7,15}'
)
LINKEDIN_PATTERN = re.compile(
    r'https?://(?:www\.)?linkedin\.com/(?:in|company)/[A-Za-z0-9_-]+'
)
TWITTER_PATTERN = re.compile(
    r'https?://(?:www\.)?(?:twitter|x)\.com/[A-Za-z0-9_]+'
)


class WebsiteScraper(BaseScraper):
    """
    Scrapes websites for contact information, emails, phone numbers,
    social media links, and company data.
    """

    async def scrape(
        self,
        url: str,
        depth: int = 2,
        max_pages: int = 20,
        extract_emails: bool = True,
        extract_phones: bool = True,
        extract_social: bool = True,
        extract_meta: bool = True,
        target_pages: Optional[List[str]] = None,
    ) -> ScraperResult:
        """
        Scrape a website for lead data.

        Args:
            url: Starting URL to scrape
            depth: How many links deep to follow (1 = only landing page)
            max_pages: Maximum number of pages to scrape
            extract_emails: Whether to find email addresses
            extract_phones: Whether to find phone numbers
            extract_social: Whether to find social media links
            extract_meta: Whether to extract page metadata
            target_pages: Specific page paths to prioritize (e.g., ["/about", "/contact", "/team"])
        """
        parsed = urlparse(url)
        base_domain = f"{parsed.scheme}://{parsed.netloc}"

        # Pages to prioritize for contact info
        priority_paths = target_pages or [
            "/contact", "/about", "/team", "/people",
            "/about-us", "/contact-us", "/our-team",
            "/leadership", "/company", "/staff",
        ]

        visited: Set[str] = set()
        to_visit: List[tuple] = [(url, 0)]  # (url, current_depth)
        all_emails: Set[str] = set()
        all_phones: Set[str] = set()
        all_social: Dict[str, Set[str]] = {"linkedin": set(), "twitter": set(), "facebook": set(), "github": set()}
        all_people: List[Dict] = []
        company_info: Dict = {}
        page_data: List[Dict] = []

        # Add priority pages to visit list
        for path in priority_paths:
            priority_url = urljoin(base_domain, path)
            to_visit.insert(0, (priority_url, 0))

        while to_visit and len(visited) < max_pages:
            current_url, current_depth = to_visit.pop(0)

            if current_url in visited:
                continue
            if not current_url.startswith(base_domain):
                continue

            visited.add(current_url)

            try:
                response = await self.fetch(current_url)
                html = response.text
                soup = BeautifulSoup(html, 'lxml')

                page_info = {"url": current_url, "title": "", "emails": [], "phones": []}

                # Extract meta info
                if extract_meta:
                    page_info["title"] = self._get_title(soup)
                    if current_url == url:
                        company_info = self._extract_company_meta(soup, base_domain)

                # Extract emails
                if extract_emails:
                    emails = self._extract_emails(html, soup)
                    all_emails.update(emails)
                    page_info["emails"] = list(emails)

                # Extract phones
                if extract_phones:
                    phones = self._extract_phones(html, soup)
                    all_phones.update(phones)
                    page_info["phones"] = list(phones)

                # Extract social links
                if extract_social:
                    social = self._extract_social_links(soup)
                    for platform, links in social.items():
                        all_social[platform].update(links)

                # Extract people/team members
                people = self._extract_people(soup, current_url)
                all_people.extend(people)

                page_data.append(page_info)

                # Find links to follow
                if current_depth < depth:
                    links = self._extract_links(soup, base_domain)
                    for link in links:
                        if link not in visited:
                            to_visit.append((link, current_depth + 1))

            except Exception as e:
                logger.warning("page_scrape_failed", url=current_url, error=str(e))
                continue

        # Compile results
        results = {
            "domain": parsed.netloc,
            "url": url,
            "pages_scraped": len(visited),
            "company_info": company_info,
            "emails": list(all_emails),
            "phones": list(all_phones),
            "social_links": {k: list(v) for k, v in all_social.items()},
            "people": all_people,
            "pages": page_data,
        }

        return ScraperResult(
            success=True,
            data=[results],
            records_found=len(all_emails) + len(all_people),
            metadata={"pages_scraped": len(visited), "depth": depth},
        )

    def _get_title(self, soup: BeautifulSoup) -> str:
        title_tag = soup.find("title")
        return title_tag.get_text(strip=True) if title_tag else ""

    def _extract_company_meta(self, soup: BeautifulSoup, base_domain: str) -> Dict:
        """Extract company info from meta tags and structured data."""
        info = {"domain": urlparse(base_domain).netloc}

        # Meta description
        desc_tag = soup.find("meta", attrs={"name": "description"})
        if desc_tag:
            info["description"] = desc_tag.get("content", "")

        # OG tags
        og_name = soup.find("meta", attrs={"property": "og:site_name"})
        if og_name:
            info["name"] = og_name.get("content", "")

        og_image = soup.find("meta", attrs={"property": "og:image"})
        if og_image:
            info["logo_url"] = og_image.get("content", "")

        # Schema.org structured data
        scripts = soup.find_all("script", {"type": "application/ld+json"})
        for script in scripts:
            try:
                import json
                data = json.loads(script.string)
                if isinstance(data, dict):
                    if data.get("@type") == "Organization":
                        info["name"] = info.get("name") or data.get("name")
                        info["logo_url"] = info.get("logo_url") or data.get("logo", {}).get("url")
                        info["address"] = data.get("address", {})
            except:
                pass

        return info

    def _extract_emails(self, html: str, soup: BeautifulSoup) -> Set[str]:
        """Extract emails from HTML text and mailto links."""
        emails = set()

        # From raw text
        found = EMAIL_PATTERN.findall(html)
        emails.update(found)

        # From mailto links
        mailto_links = soup.find_all("a", href=re.compile(r'^mailto:'))
        for link in mailto_links:
            email = link.get("href", "").replace("mailto:", "").split("?")[0]
            if email:
                emails.add(email)

        # Filter out common non-person emails
        noise = {"noreply", "no-reply", "info@example", "test@", "admin@example"}
        emails = {e.lower() for e in emails if not any(n in e.lower() for n in noise)}

        return emails

    def _extract_phones(self, html: str, soup: BeautifulSoup) -> Set[str]:
        """Extract phone numbers."""
        phones = set()

        # From tel: links
        tel_links = soup.find_all("a", href=re.compile(r'^tel:'))
        for link in tel_links:
            phone = link.get("href", "").replace("tel:", "").strip()
            if phone:
                phones.add(phone)

        # From text
        found = PHONE_PATTERN.findall(html)
        for phone in found:
            cleaned = re.sub(r'[^\d+]', '', phone)
            if len(cleaned) >= 7:
                phones.add(phone.strip())

        return phones

    def _extract_social_links(self, soup: BeautifulSoup) -> Dict[str, Set[str]]:
        """Extract social media profile links."""
        social = {"linkedin": set(), "twitter": set(), "facebook": set(), "github": set()}

        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "linkedin.com" in href:
                social["linkedin"].add(href)
            elif "twitter.com" in href or "x.com" in href:
                social["twitter"].add(href)
            elif "facebook.com" in href:
                social["facebook"].add(href)
            elif "github.com" in href:
                social["github"].add(href)

        return social

    def _extract_people(self, soup: BeautifulSoup, page_url: str) -> List[Dict]:
        """Try to extract team/people info from about/team pages."""
        people = []

        # Look for common team member patterns
        # Pattern 1: Cards with image + name + title
        team_sections = soup.find_all(["div", "section"], class_=re.compile(
            r'team|staff|people|leadership|member|card', re.I
        ))

        for section in team_sections:
            cards = section.find_all(["div", "article", "li"], class_=re.compile(
                r'member|person|card|team', re.I
            ))
            for card in cards:
                person = {}
                # Name
                name_tag = card.find(["h2", "h3", "h4", "strong"], class_=re.compile(r'name|title', re.I))
                if not name_tag:
                    name_tag = card.find(["h2", "h3", "h4"])
                if name_tag:
                    person["name"] = name_tag.get_text(strip=True)

                # Title/role
                role_tag = card.find(["p", "span", "div"], class_=re.compile(r'role|title|position|job', re.I))
                if role_tag:
                    person["job_title"] = role_tag.get_text(strip=True)

                # LinkedIn
                linkedin = card.find("a", href=re.compile(r'linkedin\.com'))
                if linkedin:
                    person["linkedin_url"] = linkedin["href"]

                # Email
                email_link = card.find("a", href=re.compile(r'^mailto:'))
                if email_link:
                    person["email"] = email_link["href"].replace("mailto:", "").split("?")[0]

                if person.get("name"):
                    person["source_url"] = page_url
                    people.append(person)

        return people

    def _extract_links(self, soup: BeautifulSoup, base_domain: str) -> List[str]:
        """Extract internal links for crawling."""
        links = []
        for a in soup.find_all("a", href=True):
            href = a["href"]
            full_url = urljoin(base_domain, href)
            parsed = urlparse(full_url)

            # Only follow internal links, skip files/anchors
            if full_url.startswith(base_domain):
                skip_extensions = ('.pdf', '.jpg', '.png', '.gif', '.zip', '.doc', '.css', '.js')
                if not any(parsed.path.endswith(ext) for ext in skip_extensions):
                    clean_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
                    links.append(clean_url)

        return list(set(links))
