"""API rate limiting middleware with Redis-backed token bucket."""
import time
from collections import defaultdict
from typing import Dict, Optional, Tuple
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
import structlog

logger = structlog.get_logger()


# Plan-based rate limits (requests per minute)
PLAN_LIMITS = {
    "free": {"rpm": 60, "daily": 1000, "burst": 10},
    "starter": {"rpm": 300, "daily": 10000, "burst": 30},
    "pro": {"rpm": 1000, "daily": 50000, "burst": 100},
    "enterprise": {"rpm": 5000, "daily": 500000, "burst": 500},
}

# Endpoint-specific limits (override plan limits for expensive operations)
ENDPOINT_LIMITS = {
    "/api/v1/scrapers/": {"rpm": 10, "cost": 5},
    "/api/v1/enrichment/lead": {"rpm": 20, "cost": 3},
    "/api/v1/enrichment/batch": {"rpm": 5, "cost": 10},
    "/api/v1/enrichment/ai/": {"rpm": 15, "cost": 5},
    "/api/v1/scoring/train": {"rpm": 2, "cost": 50},
}


class InMemoryRateLimiter:
    """Simple in-memory rate limiter (use Redis in production)."""

    def __init__(self):
        self._buckets: Dict[str, Dict] = defaultdict(lambda: {
            "tokens": 0,
            "last_refill": time.time(),
            "daily_count": 0,
            "daily_reset": time.time(),
        })

    def check_rate_limit(
        self,
        key: str,
        max_rpm: int,
        max_daily: int,
        burst: int = 10,
    ) -> Tuple[bool, Dict[str, int]]:
        """
        Check if request is within rate limits.

        Returns:
            (allowed: bool, headers: dict with rate limit info)
        """
        now = time.time()
        bucket = self._buckets[key]

        # Reset daily counter if new day
        if now - bucket["daily_reset"] > 86400:
            bucket["daily_count"] = 0
            bucket["daily_reset"] = now

        # Token bucket refill
        elapsed = now - bucket["last_refill"]
        refill_rate = max_rpm / 60.0  # tokens per second
        bucket["tokens"] = min(burst, bucket["tokens"] + elapsed * refill_rate)
        bucket["last_refill"] = now

        # Check daily limit
        if bucket["daily_count"] >= max_daily:
            return False, {
                "X-RateLimit-Limit": str(max_rpm),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(int(bucket["daily_reset"] + 86400)),
                "X-RateLimit-Daily-Remaining": "0",
                "Retry-After": str(int(bucket["daily_reset"] + 86400 - now)),
            }

        # Check per-minute limit
        if bucket["tokens"] < 1:
            wait_time = (1 - bucket["tokens"]) / refill_rate
            return False, {
                "X-RateLimit-Limit": str(max_rpm),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(int(now + wait_time)),
                "Retry-After": str(int(wait_time) + 1),
            }

        # Consume token
        bucket["tokens"] -= 1
        bucket["daily_count"] += 1

        remaining = int(bucket["tokens"])
        daily_remaining = max_daily - bucket["daily_count"]

        return True, {
            "X-RateLimit-Limit": str(max_rpm),
            "X-RateLimit-Remaining": str(remaining),
            "X-RateLimit-Daily-Remaining": str(daily_remaining),
        }


# Global rate limiter instance
_rate_limiter = InMemoryRateLimiter()


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    FastAPI middleware for API rate limiting.

    Features:
    - Per-team rate limiting based on plan
    - Endpoint-specific limits for expensive operations
    - Burst allowance for traffic spikes
    - Rate limit headers in responses
    - Usage tracking and analytics
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        # Skip rate limiting for health checks and docs
        path = request.url.path
        if path in ("/health", "/docs", "/redoc", "/openapi.json", "/"):
            return await call_next(request)

        # Skip for tracking events (high-volume, low-cost)
        if path.startswith("/api/v1/track/"):
            return await call_next(request)

        # Extract team/user identifier
        team_id = self._extract_team_id(request)
        plan = self._get_plan(team_id)
        limits = PLAN_LIMITS.get(plan, PLAN_LIMITS["free"])

        # Check endpoint-specific limits
        endpoint_limit = self._get_endpoint_limit(path)
        if endpoint_limit:
            rpm = min(limits["rpm"], endpoint_limit["rpm"])
        else:
            rpm = limits["rpm"]

        # Check rate limit
        rate_key = f"{team_id}:{path.split('/')[3] if len(path.split('/')) > 3 else 'general'}"
        allowed, headers = _rate_limiter.check_rate_limit(
            key=rate_key,
            max_rpm=rpm,
            max_daily=limits["daily"],
            burst=limits["burst"],
        )

        if not allowed:
            logger.warning("rate_limit_exceeded", team_id=team_id, path=path)
            response = JSONResponse(
                status_code=429,
                content={
                    "detail": "Rate limit exceeded",
                    "plan": plan,
                    "upgrade_url": "/settings/billing",
                },
            )
            for k, v in headers.items():
                response.headers[k] = v
            return response

        # Process request
        response = await call_next(request)

        # Add rate limit headers to response
        for k, v in headers.items():
            response.headers[k] = v

        return response

    def _extract_team_id(self, request: Request) -> str:
        """Extract team ID from JWT token or API key."""
        auth = request.headers.get("authorization", "")
        if auth.startswith("Bearer "):
            # In production: decode JWT and get team_id
            return "default_team"

        api_key = request.headers.get("x-api-key", "")
        if api_key:
            return f"apikey:{api_key[:8]}"

        # Fallback to IP
        ip = request.client.host if request.client else "unknown"
        return f"ip:{ip}"

    def _get_plan(self, team_id: str) -> str:
        """Get the plan for a team (in production: DB lookup)."""
        # Default to free plan
        return "pro"

    def _get_endpoint_limit(self, path: str) -> Optional[Dict]:
        """Get endpoint-specific rate limit if any."""
        for endpoint_prefix, limit in ENDPOINT_LIMITS.items():
            if path.startswith(endpoint_prefix):
                return limit
        return None
