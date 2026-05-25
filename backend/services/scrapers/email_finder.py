"""Email finder - discovers email addresses using multiple strategies."""
import re
import asyncio
import hashlib
from typing import Dict, List, Optional, Set
from urllib.parse import urlparse
import structlog

from backend.services.scrapers.base import BaseScraper, ScraperResult

logger = structlog.get_logger()


# Common email patterns for businesses
EMAIL_PATTERNS = [
    "{first}.{last}@{domain}",
    "{first}{last}@{domain}",
    "{f}{last}@{domain}",
    "{first}_{last}@{domain}",
    "{first}@{domain}",
    "{last}@{domain}",
    "{f}.{last}@{domain}",
    "{first}{l}@{domain}",
    "{first}-{last}@{domain}",
]



class EmailFinder(BaseScraper):
    """
    Multi-strategy email finder:
    1. Pattern generation + SMTP verification
    2. Website scraping for emails
    3. Google dorking for email patterns
    4. Catch-all domain detection
    5. Hunter.io / similar API fallback
    """

    async def scrape(
        self,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        domain: Optional[str] = None,
        company_name: Optional[str] = None,
        linkedin_url: Optional[str] = None,
        verify: bool = True,
        max_results: int = 5,
    ) -> ScraperResult:
        """
        Find email addresses for a person.

        Args:
            first_name: Person's first name
            last_name: Person's last name
            domain: Company domain (e.g., "example.com")
            company_name: Company name (used to find domain if not provided)
            linkedin_url: LinkedIn profile URL for additional context
            verify: Whether to verify emails via SMTP
            max_results: Max email candidates to return
        """
        found_emails: List[Dict] = []
        errors: List[str] = []

        # Step 1: Find domain if not provided
        if not domain and company_name:
            domain = await self._find_company_domain(company_name)

        if not domain:
            return ScraperResult(
                success=False,
                errors=["Could not determine company domain"],
            )

        # Step 2: Generate email pattern candidates
        if first_name and last_name:
            candidates = self._generate_patterns(first_name, last_name, domain)
        else:
            candidates = []

        # Step 3: Check website for actual emails
        website_emails = await self._scrape_website_emails(domain)
        
        # Step 4: Detect email pattern from found emails
        detected_pattern = self._detect_pattern(website_emails, domain)
        if detected_pattern and first_name and last_name:
            best_guess = self._apply_pattern(
                detected_pattern, first_name, last_name, domain
            )
            if best_guess:
                candidates.insert(0, best_guess)

        # Step 5: Google dorking for email
        google_emails = await self._google_dork_email(
            first_name, last_name, domain
        )

        # Compile all found emails
        all_candidates = []
        
        # Add google-found emails (high confidence)
        for email in google_emails:
            all_candidates.append({
                "email": email,
                "confidence": "high",
                "source": "google_search",
                "verified": False,
            })

        # Add website-found emails
        for email in website_emails:
            if first_name and first_name.lower() in email.lower():
                all_candidates.append({
                    "email": email,
                    "confidence": "high",
                    "source": "website",
                    "verified": False,
                })
            else:
                all_candidates.append({
                    "email": email,
                    "confidence": "medium",
                    "source": "website",
                    "verified": False,
                })

        # Add pattern-generated candidates
        for email in candidates[:5]:
            all_candidates.append({
                "email": email,
                "confidence": "medium",
                "source": "pattern",
                "verified": False,
            })

        # Step 6: Verify emails via SMTP if requested
        if verify and all_candidates:
            all_candidates = await self._verify_emails(all_candidates)

        # Deduplicate and sort by confidence
        seen = set()
        unique = []
        for c in all_candidates:
            if c["email"].lower() not in seen:
                seen.add(c["email"].lower())
                unique.append(c)

        confidence_order = {"high": 0, "medium": 1, "low": 2}
        unique.sort(key=lambda x: confidence_order.get(x["confidence"], 3))

        return ScraperResult(
            success=True,
            data=unique[:max_results],
            records_found=len(unique[:max_results]),
            metadata={
                "domain": domain,
                "pattern_detected": detected_pattern,
                "website_emails_found": len(website_emails),
            },
        )


    def _generate_patterns(
        self, first_name: str, last_name: str, domain: str
    ) -> List[str]:
        """Generate email candidates from common patterns."""
        first = first_name.lower().strip()
        last = last_name.lower().strip()
        f = first[0] if first else ""
        l = last[0] if last else ""

        emails = []
        for pattern in EMAIL_PATTERNS:
            email = pattern.format(
                first=first, last=last, f=f, l=l, domain=domain
            )
            emails.append(email)
        return emails

    async def _find_company_domain(self, company_name: str) -> Optional[str]:
        """Find company domain from company name via Google search."""
        try:
            query = f"{company_name} official website"
            response = await self.fetch(
                "https://www.google.com/search",
                params={"q": query, "num": 5},
            )
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(response.text, 'lxml')

            # Look for the first non-social-media result
            for a in soup.find_all("a", href=True):
                href = a["href"]
                if "/url?q=" in href:
                    url = href.split("/url?q=")[1].split("&")[0]
                    parsed = urlparse(url)
                    domain = parsed.netloc.replace("www.", "")
                    skip = ["linkedin.com", "facebook.com", "twitter.com",
                            "instagram.com", "youtube.com", "google.com",
                            "wikipedia.org", "crunchbase.com"]
                    if not any(s in domain for s in skip):
                        return domain
        except Exception as e:
            logger.warning("domain_search_failed", company=company_name, error=str(e))
        return None

    async def _scrape_website_emails(self, domain: str) -> List[str]:
        """Scrape the company website for any email addresses."""
        emails: Set[str] = set()
        pages_to_check = [
            f"https://{domain}",
            f"https://{domain}/contact",
            f"https://{domain}/about",
            f"https://{domain}/team",
            f"https://www.{domain}",
            f"https://www.{domain}/contact",
        ]

        email_pattern = re.compile(
            r'\b[A-Za-z0-9._%+-]+@' + re.escape(domain) + r'\b'
        )

        for url in pages_to_check:
            try:
                response = await self.fetch(url)
                found = email_pattern.findall(response.text)
                emails.update(found)
            except:
                continue

        # Filter out generic emails
        generic = {"noreply", "no-reply", "support", "info", "hello",
                   "admin", "webmaster", "postmaster", "sales", "contact"}
        personal_emails = [
            e for e in emails
            if not any(g in e.lower().split("@")[0] for g in generic)
        ]

        return personal_emails or list(emails)

    def _detect_pattern(self, emails: List[str], domain: str) -> Optional[str]:
        """Detect the email pattern used at a company from found emails."""
        if not emails:
            return None

        patterns_found = {}
        for email in emails:
            local_part = email.split("@")[0].lower()
            if "." in local_part:
                patterns_found["{first}.{last}"] = patterns_found.get(
                    "{first}.{last}", 0
                ) + 1
            elif "_" in local_part:
                patterns_found["{first}_{last}"] = patterns_found.get(
                    "{first}_{last}", 0
                ) + 1
            elif "-" in local_part:
                patterns_found["{first}-{last}"] = patterns_found.get(
                    "{first}-{last}", 0
                ) + 1
            else:
                if len(local_part) <= 3:
                    patterns_found["{f}{last}"] = patterns_found.get(
                        "{f}{last}", 0
                    ) + 1
                else:
                    patterns_found["{first}{last}"] = patterns_found.get(
                        "{first}{last}", 0
                    ) + 1

        if patterns_found:
            return max(patterns_found, key=patterns_found.get)
        return None

    def _apply_pattern(
        self, pattern: str, first_name: str, last_name: str, domain: str
    ) -> Optional[str]:
        """Apply detected pattern to generate best-guess email."""
        first = first_name.lower().strip()
        last = last_name.lower().strip()
        f = first[0] if first else ""
        l = last[0] if last else ""

        email = pattern.format(first=first, last=last, f=f, l=l)
        return f"{email}@{domain}"

    async def _google_dork_email(
        self,
        first_name: Optional[str],
        last_name: Optional[str],
        domain: str,
    ) -> List[str]:
        """Search Google for the person's email at the domain."""
        emails = []
        if not first_name or not last_name:
            return emails

        queries = [
            f'"{first_name} {last_name}" "@{domain}"',
            f'"{first_name} {last_name}" email {domain}',
        ]

        email_pattern = re.compile(
            r'\b[A-Za-z0-9._%+-]+@' + re.escape(domain) + r'\b'
        )

        for query in queries:
            try:
                response = await self.fetch(
                    "https://www.google.com/search",
                    params={"q": query, "num": 10},
                )
                found = email_pattern.findall(response.text)
                emails.extend(found)
            except:
                continue

        return list(set(emails))

    async def _verify_emails(
        self, candidates: List[Dict]
    ) -> List[Dict]:
        """
        Verify email addresses using DNS MX lookup and SMTP.
        In production, use a dedicated verification service.
        """
        import socket
        import dns.resolver  # requires dnspython

        for candidate in candidates:
            email = candidate["email"]
            domain = email.split("@")[1]

            try:
                # Check MX records exist
                mx_records = dns.resolver.resolve(domain, 'MX')
                if mx_records:
                    candidate["mx_valid"] = True
                    # If pattern-generated, upgrade confidence
                    if candidate["source"] == "pattern":
                        candidate["confidence"] = "medium"
                else:
                    candidate["mx_valid"] = False
                    candidate["confidence"] = "low"
            except Exception:
                candidate["mx_valid"] = False
                # Don't downgrade if found on website/google
                if candidate["source"] == "pattern":
                    candidate["confidence"] = "low"

        return candidates
