"""Base scraper framework with retry logic, rate limiting, and proxy rotation."""
import asyncio
import random
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from datetime import datetime
import httpx
import structlog

logger = structlog.get_logger()


@dataclass
class ScraperResult:
    """Standard result format for all scrapers."""
    success: bool
    data: List[Dict[str, Any]] = field(default_factory=list)
    records_found: int = 0
    errors: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    duration_seconds: float = 0.0
    requests_made: int = 0
    source: str = ""


class RateLimiter:
    """Token bucket rate limiter."""

    def __init__(self, requests_per_second: float = 1.0, burst: int = 5):
        self.rate = requests_per_second
        self.burst = burst
        self.tokens = burst
        self.last_refill = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self):
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self.last_refill
            self.tokens = min(self.burst, self.tokens + elapsed * self.rate)
            self.last_refill = now

            if self.tokens < 1:
                wait_time = (1 - self.tokens) / self.rate
                await asyncio.sleep(wait_time)
                self.tokens = 0
            else:
                self.tokens -= 1


class ProxyRotator:
    """Rotate through proxy list to avoid IP blocks."""

    def __init__(self, proxies: Optional[List[str]] = None):
        self.proxies = proxies or []
        self.current_index = 0
        self.failed_proxies: set = set()

    def get_proxy(self) -> Optional[str]:
        if not self.proxies:
            return None

        available = [p for p in self.proxies if p not in self.failed_proxies]
        if not available:
            # Reset failed proxies if all have failed
            self.failed_proxies.clear()
            available = self.proxies

        proxy = random.choice(available)
        return proxy

    def mark_failed(self, proxy: str):
        self.failed_proxies.add(proxy)


USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
]


class BaseScraper(ABC):
    """Base class for all scrapers with built-in resilience."""

    def __init__(
        self,
        rate_limit: float = 1.0,
        max_retries: int = 3,
        timeout: int = 30,
        proxies: Optional[List[str]] = None,
    ):
        self.rate_limiter = RateLimiter(requests_per_second=rate_limit)
        self.proxy_rotator = ProxyRotator(proxies)
        self.max_retries = max_retries
        self.timeout = timeout
        self.requests_made = 0
        self._client: Optional[httpx.AsyncClient] = None

    @property
    def source_name(self) -> str:
        return self.__class__.__name__

    async def get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            proxy = self.proxy_rotator.get_proxy()
            self._client = httpx.AsyncClient(
                timeout=self.timeout,
                proxy=proxy,
                headers=self._get_headers(),
                follow_redirects=True,
            )
        return self._client

    def _get_headers(self) -> Dict[str, str]:
        return {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Cache-Control": "no-cache",
        }

    async def fetch(self, url: str, **kwargs) -> httpx.Response:
        """Fetch URL with rate limiting and retries."""
        await self.rate_limiter.acquire()

        for attempt in range(self.max_retries):
            try:
                client = await self.get_client()
                response = await client.get(url, **kwargs)
                self.requests_made += 1

                if response.status_code == 429:
                    # Rate limited - exponential backoff
                    wait = (2 ** attempt) + random.uniform(1, 3)
                    logger.warning("rate_limited", url=url, wait=wait)
                    await asyncio.sleep(wait)
                    continue

                if response.status_code == 403:
                    # Possibly blocked - rotate proxy
                    logger.warning("blocked", url=url, attempt=attempt)
                    proxy = self.proxy_rotator.get_proxy()
                    if proxy:
                        self.proxy_rotator.mark_failed(proxy)
                    await self._reset_client()
                    continue

                response.raise_for_status()
                return response

            except httpx.TimeoutException:
                logger.warning("timeout", url=url, attempt=attempt)
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
            except httpx.HTTPStatusError as e:
                logger.error("http_error", url=url, status=e.response.status_code)
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
            except Exception as e:
                logger.error("fetch_error", url=url, error=str(e))
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(1)

        raise Exception(f"Failed to fetch {url} after {self.max_retries} attempts")

    async def fetch_post(self, url: str, data: Any = None, json: Any = None, **kwargs) -> httpx.Response:
        """POST request with rate limiting and retries."""
        await self.rate_limiter.acquire()

        for attempt in range(self.max_retries):
            try:
                client = await self.get_client()
                response = await client.post(url, data=data, json=json, **kwargs)
                self.requests_made += 1
                response.raise_for_status()
                return response
            except Exception as e:
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
                else:
                    raise

    async def _reset_client(self):
        """Reset HTTP client (e.g., after proxy rotation)."""
        if self._client:
            await self._client.aclose()
        self._client = None

    async def close(self):
        """Clean up resources."""
        if self._client:
            await self._client.aclose()

    @abstractmethod
    async def scrape(self, **kwargs) -> ScraperResult:
        """Execute the scraping job. Must be implemented by subclasses."""
        pass

    async def run(self, **kwargs) -> ScraperResult:
        """Execute scrape with timing and error handling."""
        start = time.time()
        try:
            result = await self.scrape(**kwargs)
            result.duration_seconds = time.time() - start
            result.requests_made = self.requests_made
            result.source = self.source_name
            return result
        except Exception as e:
            logger.error("scraper_failed", scraper=self.source_name, error=str(e))
            return ScraperResult(
                success=False,
                errors=[str(e)],
                duration_seconds=time.time() - start,
                requests_made=self.requests_made,
                source=self.source_name,
            )
        finally:
            await self.close()
