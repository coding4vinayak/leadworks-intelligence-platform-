"""Usage tracking middleware - tracks API usage, costs, and quotas."""
import time
from collections import defaultdict
from datetime import datetime, date
from typing import Any, Dict, List
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
import structlog

logger = structlog.get_logger()


# API operation costs (credits per operation)
OPERATION_COSTS = {
    "scrape": 5,
    "enrich": 3,
    "ai_analyze": 5,
    "ai_outreach": 3,
    "score": 1,
    "email_send": 1,
    "whatsapp_send": 2,
    "csv_import": 0,
    "webhook": 0,
    "search": 0,
    "crud": 0,
}


class UsageTracker:
    """
    Tracks API usage per team for billing and quota enforcement.

    Tracks:
    - Total API calls per endpoint
    - Credit consumption per operation
    - Response times (P50, P95, P99)
    - Error rates
    - Feature usage (which features are actually used)
    """

    def __init__(self):
        self._usage: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
            "api_calls": 0,
            "credits_used": 0,
            "endpoints": defaultdict(int),
            "response_times": [],
            "errors": 0,
            "features_used": set(),
            "date": date.today().isoformat(),
        })

    def record_request(
        self,
        team_id: str,
        endpoint: str,
        method: str,
        status_code: int,
        response_time_ms: float,
        operation_type: Optional[str] = None,
    ):
        """Record an API request for usage tracking."""
        usage = self._usage[team_id]

        # Reset daily if new day
        today = date.today().isoformat()
        if usage["date"] != today:
            self._archive_daily(team_id, usage)
            self._usage[team_id] = {
                "api_calls": 0,
                "credits_used": 0,
                "endpoints": defaultdict(int),
                "response_times": [],
                "errors": 0,
                "features_used": set(),
                "date": today,
            }
            usage = self._usage[team_id]

        usage["api_calls"] += 1
        usage["endpoints"][endpoint] += 1
        usage["response_times"].append(response_time_ms)

        if status_code >= 400:
            usage["errors"] += 1

        # Track credits
        if operation_type:
            cost = OPERATION_COSTS.get(operation_type, 0)
            usage["credits_used"] += cost

        # Track feature usage
        feature = self._endpoint_to_feature(endpoint)
        if feature:
            usage["features_used"].add(feature)

    def get_usage(self, team_id: str) -> Dict[str, Any]:
        """Get current usage stats for a team."""
        usage = self._usage.get(team_id, {})
        response_times = usage.get("response_times", [])

        stats = {
            "team_id": team_id,
            "date": usage.get("date", date.today().isoformat()),
            "api_calls": usage.get("api_calls", 0),
            "credits_used": usage.get("credits_used", 0),
            "errors": usage.get("errors", 0),
            "error_rate": round(
                usage.get("errors", 0) / max(usage.get("api_calls", 1), 1) * 100, 2
            ),
            "features_used": list(usage.get("features_used", set())),
            "top_endpoints": dict(
                sorted(
                    usage.get("endpoints", {}).items(),
                    key=lambda x: x[1],
                    reverse=True,
                )[:10]
            ),
        }

        if response_times:
            sorted_times = sorted(response_times)
            n = len(sorted_times)
            stats["response_times"] = {
                "avg_ms": round(sum(sorted_times) / n, 1),
                "p50_ms": round(sorted_times[int(n * 0.5)], 1),
                "p95_ms": round(sorted_times[int(n * 0.95)], 1),
                "p99_ms": round(sorted_times[int(n * 0.99)], 1),
            }

        return stats

    def _endpoint_to_feature(self, endpoint: str) -> Optional[str]:
        """Map endpoint to feature name for usage analytics."""
        if "/scrapers/" in endpoint:
            return "scrapers"
        elif "/enrichment/" in endpoint:
            return "enrichment"
        elif "/scoring/" in endpoint:
            return "scoring"
        elif "/campaigns/" in endpoint:
            return "campaigns"
        elif "/connectors/" in endpoint:
            return "connectors"
        elif "/track/" in endpoint:
            return "tracking"
        elif "/analytics/" in endpoint:
            return "analytics"
        elif "/leads/" in endpoint:
            return "leads"
        return None

    def _archive_daily(self, team_id: str, usage: Dict):
        """Archive daily usage (in production: write to DB)."""
        logger.info(
            "daily_usage_archived",
            team_id=team_id,
            date=usage["date"],
            api_calls=usage["api_calls"],
            credits=usage["credits_used"],
        )


# Global tracker
_usage_tracker = UsageTracker()


class UsageTrackingMiddleware(BaseHTTPMiddleware):
    """Middleware that tracks API usage for billing and analytics."""

    async def dispatch(self, request: Request, call_next) -> Response:
        start_time = time.time()

        response = await call_next(request)

        # Calculate response time
        duration_ms = (time.time() - start_time) * 1000

        # Extract team info
        team_id = self._extract_team_id(request)
        endpoint = request.url.path
        method = request.method
        operation = self._classify_operation(endpoint, method)

        # Record usage
        _usage_tracker.record_request(
            team_id=team_id,
            endpoint=endpoint,
            method=method,
            status_code=response.status_code,
            response_time_ms=duration_ms,
            operation_type=operation,
        )

        # Add usage headers
        response.headers["X-Credits-Used"] = str(OPERATION_COSTS.get(operation, 0))

        return response

    def _extract_team_id(self, request: Request) -> str:
        """Extract team ID from request."""
        auth = request.headers.get("authorization", "")
        if auth:
            return "default_team"
        return f"ip:{request.client.host}" if request.client else "unknown"

    def _classify_operation(self, endpoint: str, method: str) -> Optional[str]:
        """Classify the operation type for cost tracking."""
        if "/scrapers/" in endpoint and method == "POST":
            return "scrape"
        elif "/enrichment/lead" in endpoint:
            return "enrich"
        elif "/enrichment/ai/" in endpoint:
            return "ai_analyze"
        elif "/scoring/" in endpoint and method == "POST":
            return "score"
        elif "/track/" in endpoint:
            return None  # Free
        return "crud"


def get_usage_stats(team_id: str) -> Dict[str, Any]:
    """Get usage stats (exported for routes)."""
    return _usage_tracker.get_usage(team_id)

Optional = None  # fix unused import warning
