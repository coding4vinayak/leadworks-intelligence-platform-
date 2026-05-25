"""API Routes for Leadworks Intelligence Platform."""
from backend.routes.auth import router as auth_router
from backend.routes.leads import router as leads_router
from backend.routes.companies import router as companies_router
from backend.routes.scrapers import router as scrapers_router
from backend.routes.connectors import router as connectors_router
from backend.routes.enrichment import router as enrichment_router
from backend.routes.scoring import router as scoring_router
from backend.routes.campaigns import router as campaigns_router
from backend.routes.webhooks import router as webhooks_router
from backend.routes.analytics import router as analytics_router

__all__ = [
    "auth_router", "leads_router", "companies_router",
    "scrapers_router", "connectors_router", "enrichment_router",
    "scoring_router", "campaigns_router", "webhooks_router",
    "analytics_router",
]
