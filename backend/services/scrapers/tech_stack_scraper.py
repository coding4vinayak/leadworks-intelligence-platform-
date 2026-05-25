"""Tech stack scraper - detects technologies used by a company."""
import re
from typing import Dict, List, Optional, Set
from urllib.parse import urlparse
from bs4 import BeautifulSoup
import structlog

from backend.services.scrapers.base import BaseScraper, ScraperResult

logger = structlog.get_logger()


# Technology signatures to detect from HTML/headers
TECH_SIGNATURES = {
    # Frontend frameworks
    "React": [r'react', r'_next', r'__NEXT_DATA__', r'reactroot'],
    "Vue.js": [r'vue', r'__vue__', r'v-app'],
    "Angular": [r'ng-version', r'ng-app', r'angular'],
    "Svelte": [r'svelte', r'__svelte'],
    "Next.js": [r'_next/static', r'__NEXT_DATA__'],
    "Nuxt.js": [r'__nuxt', r'_nuxt'],
    "Gatsby": [r'gatsby', r'___gatsby'],

    # CMS
    "WordPress": [r'wp-content', r'wp-includes', r'wordpress'],
    "Shopify": [r'shopify', r'cdn\.shopify\.com'],
    "Webflow": [r'webflow', r'wf-'],
    "Squarespace": [r'squarespace', r'static\.squarespace'],
    "Wix": [r'wix\.com', r'wixstatic'],
    "Drupal": [r'drupal', r'/sites/default/files'],
    "HubSpot CMS": [r'hs-scripts', r'hubspot'],

    # Analytics & Marketing
    "Google Analytics": [r'google-analytics', r'gtag', r'UA-\d+', r'G-\w+'],
    "Google Tag Manager": [r'googletagmanager', r'GTM-\w+'],
    "Hotjar": [r'hotjar', r'hj\('],
    "Segment": [r'segment\.com', r'analytics\.js'],
    "Mixpanel": [r'mixpanel'],
    "Amplitude": [r'amplitude'],
    "Heap": [r'heap', r'heapanalytics'],
    "Intercom": [r'intercom', r'intercomSettings'],
    "Drift": [r'drift\.com', r'driftt'],
    "HubSpot": [r'hubspot', r'hs-analytics'],

    # Hosting/CDN
    "Cloudflare": [r'cloudflare', r'cf-ray'],
    "AWS": [r'amazonaws\.com', r'aws'],
    "Vercel": [r'vercel', r'\.vercel\.app'],
    "Netlify": [r'netlify'],
    "Heroku": [r'herokuapp'],
    "Google Cloud": [r'googleapis', r'gstatic'],

    # Payment
    "Stripe": [r'stripe\.com', r'js\.stripe'],
    "PayPal": [r'paypal'],
    "Braintree": [r'braintree'],

    # Chat/Support
    "Zendesk": [r'zendesk', r'zdassets'],
    "Freshdesk": [r'freshdesk'],
    "Crisp": [r'crisp\.chat'],
    "LiveChat": [r'livechatinc'],

    # Email
    "Mailchimp": [r'mailchimp', r'mc\.js'],
    "SendGrid": [r'sendgrid'],
    "Mailgun": [r'mailgun'],

    # A/B Testing
    "Optimizely": [r'optimizely'],
    "VWO": [r'visualwebsiteoptimizer'],
    "Google Optimize": [r'googleoptimize'],
}



class TechStackScraper(BaseScraper):
    """
    Detects the technology stack of a company by analyzing:
    - HTML source and meta tags
    - HTTP response headers
    - JavaScript libraries loaded
    - DNS records
    - robots.txt
    """

    async def scrape(
        self,
        domain: str,
        deep_scan: bool = False,
    ) -> ScraperResult:
        """
        Detect technologies used by a domain.

        Args:
            domain: Domain to analyze (e.g., "example.com")
            deep_scan: Whether to check multiple pages
        """
        technologies: Dict[str, Dict] = {}
        errors: List[str] = []

        # Normalize domain
        if not domain.startswith("http"):
            url = f"https://{domain}"
        else:
            url = domain
            domain = urlparse(url).netloc

        # Scan homepage
        try:
            response = await self.fetch(url)
            html = response.text
            headers = dict(response.headers)

            # Detect from HTML
            html_techs = self._detect_from_html(html)
            technologies.update(html_techs)

            # Detect from headers
            header_techs = self._detect_from_headers(headers)
            technologies.update(header_techs)

            # Detect from scripts
            soup = BeautifulSoup(html, 'lxml')
            script_techs = self._detect_from_scripts(soup)
            technologies.update(script_techs)

            # Detect from meta tags
            meta_techs = self._detect_from_meta(soup)
            technologies.update(meta_techs)

        except Exception as e:
            errors.append(f"Homepage scan failed: {str(e)}")

        # Check robots.txt for hints
        try:
            robots_response = await self.fetch(f"https://{domain}/robots.txt")
            robots_techs = self._detect_from_robots(robots_response.text)
            technologies.update(robots_techs)
        except:
            pass

        # Deep scan additional pages
        if deep_scan:
            extra_pages = ["/pricing", "/blog", "/login", "/signup"]
            for page in extra_pages:
                try:
                    resp = await self.fetch(f"https://{domain}{page}")
                    extra_techs = self._detect_from_html(resp.text)
                    technologies.update(extra_techs)
                except:
                    continue

        # Categorize results
        categorized = self._categorize_technologies(technologies)

        return ScraperResult(
            success=True,
            data=[{
                "domain": domain,
                "technologies": technologies,
                "categorized": categorized,
                "tech_count": len(technologies),
            }],
            records_found=len(technologies),
            metadata={"domain": domain, "deep_scan": deep_scan},
        )

    def _detect_from_html(self, html: str) -> Dict[str, Dict]:
        """Detect technologies from HTML source."""
        found = {}
        html_lower = html.lower()

        for tech, patterns in TECH_SIGNATURES.items():
            for pattern in patterns:
                if re.search(pattern, html_lower):
                    found[tech] = {"source": "html", "confidence": "high"}
                    break
        return found

    def _detect_from_headers(self, headers: Dict) -> Dict[str, Dict]:
        """Detect technologies from HTTP headers."""
        found = {}

        # Server header
        server = headers.get("server", "").lower()
        if "nginx" in server:
            found["Nginx"] = {"source": "headers", "confidence": "high"}
        elif "apache" in server:
            found["Apache"] = {"source": "headers", "confidence": "high"}
        elif "cloudflare" in server:
            found["Cloudflare"] = {"source": "headers", "confidence": "high"}

        # X-Powered-By
        powered_by = headers.get("x-powered-by", "").lower()
        if "express" in powered_by:
            found["Express.js"] = {"source": "headers", "confidence": "high"}
        elif "php" in powered_by:
            found["PHP"] = {"source": "headers", "confidence": "high"}
        elif "asp.net" in powered_by:
            found["ASP.NET"] = {"source": "headers", "confidence": "high"}
        elif "next.js" in powered_by:
            found["Next.js"] = {"source": "headers", "confidence": "high"}

        # Cloudflare
        if "cf-ray" in headers:
            found["Cloudflare"] = {"source": "headers", "confidence": "high"}

        # Vercel
        if "x-vercel" in headers or headers.get("server") == "Vercel":
            found["Vercel"] = {"source": "headers", "confidence": "high"}

        return found

    def _detect_from_scripts(self, soup: BeautifulSoup) -> Dict[str, Dict]:
        """Detect technologies from loaded scripts."""
        found = {}
        scripts = soup.find_all("script", src=True)

        for script in scripts:
            src = script.get("src", "").lower()
            if "jquery" in src:
                found["jQuery"] = {"source": "script", "confidence": "high"}
            elif "react" in src:
                found["React"] = {"source": "script", "confidence": "high"}
            elif "vue" in src:
                found["Vue.js"] = {"source": "script", "confidence": "high"}
            elif "angular" in src:
                found["Angular"] = {"source": "script", "confidence": "high"}
            elif "bootstrap" in src:
                found["Bootstrap"] = {"source": "script", "confidence": "high"}
            elif "tailwind" in src:
                found["Tailwind CSS"] = {"source": "script", "confidence": "high"}

        return found

    def _detect_from_meta(self, soup: BeautifulSoup) -> Dict[str, Dict]:
        """Detect from meta tags."""
        found = {}
        generator = soup.find("meta", attrs={"name": "generator"})
        if generator:
            content = generator.get("content", "").lower()
            if "wordpress" in content:
                found["WordPress"] = {"source": "meta", "confidence": "high"}
            elif "drupal" in content:
                found["Drupal"] = {"source": "meta", "confidence": "high"}
            elif "joomla" in content:
                found["Joomla"] = {"source": "meta", "confidence": "high"}
            elif "hugo" in content:
                found["Hugo"] = {"source": "meta", "confidence": "high"}
            elif "ghost" in content:
                found["Ghost"] = {"source": "meta", "confidence": "high"}
        return found

    def _detect_from_robots(self, robots_txt: str) -> Dict[str, Dict]:
        """Detect technologies from robots.txt hints."""
        found = {}
        if "wp-admin" in robots_txt:
            found["WordPress"] = {"source": "robots.txt", "confidence": "high"}
        if "drupal" in robots_txt.lower():
            found["Drupal"] = {"source": "robots.txt", "confidence": "high"}
        return found

    def _categorize_technologies(self, technologies: Dict) -> Dict[str, List[str]]:
        """Categorize detected technologies."""
        categories = {
            "frontend": [], "backend": [], "cms": [],
            "analytics": [], "hosting": [], "marketing": [],
            "payment": [], "other": [],
        }

        category_map = {
            "React": "frontend", "Vue.js": "frontend", "Angular": "frontend",
            "Next.js": "frontend", "Svelte": "frontend", "jQuery": "frontend",
            "Bootstrap": "frontend", "Tailwind CSS": "frontend",
            "WordPress": "cms", "Shopify": "cms", "Webflow": "cms",
            "Drupal": "cms", "Wix": "cms",
            "Google Analytics": "analytics", "Mixpanel": "analytics",
            "Hotjar": "analytics", "Segment": "analytics",
            "Cloudflare": "hosting", "AWS": "hosting", "Vercel": "hosting",
            "Stripe": "payment", "PayPal": "payment",
            "Nginx": "backend", "Apache": "backend", "Express.js": "backend",
            "PHP": "backend", "ASP.NET": "backend",
            "HubSpot": "marketing", "Intercom": "marketing",
            "Mailchimp": "marketing",
        }

        for tech in technologies:
            cat = category_map.get(tech, "other")
            categories[cat].append(tech)

        return {k: v for k, v in categories.items() if v}
