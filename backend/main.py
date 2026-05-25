"""Leadworks Intelligence Platform - FastAPI Application."""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import structlog
import time

from backend.config import settings
from backend.routes import (
    auth_router, leads_router, companies_router,
    scrapers_router, connectors_router, enrichment_router,
    scoring_router, campaigns_router, webhooks_router,
    analytics_router,
)
from backend.routes.tracking import router as tracking_router
from backend.middleware.rate_limiter import RateLimitMiddleware
from backend.middleware.usage_tracker import UsageTrackingMiddleware

logger = structlog.get_logger()

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="AI-powered lead intelligence platform with scraping, enrichment, scoring, and automation.",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure per environment
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Middleware stack (order matters - outermost first)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(UsageTrackingMiddleware)


# Request timing middleware
@app.middleware("http")
async def add_timing_header(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    duration = time.time() - start
    response.headers["X-Response-Time"] = f"{duration:.4f}s"
    return response


# Global error handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error("unhandled_exception", error=str(exc), path=request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "type": type(exc).__name__},
    )


# Register routers
app.include_router(auth_router, prefix=f"{settings.API_PREFIX}/auth", tags=["Authentication"])
app.include_router(leads_router, prefix=f"{settings.API_PREFIX}/leads", tags=["Leads"])
app.include_router(companies_router, prefix=f"{settings.API_PREFIX}/companies", tags=["Companies"])
app.include_router(scrapers_router, prefix=f"{settings.API_PREFIX}/scrapers", tags=["Scrapers"])
app.include_router(connectors_router, prefix=f"{settings.API_PREFIX}/connectors", tags=["Connectors"])
app.include_router(enrichment_router, prefix=f"{settings.API_PREFIX}/enrichment", tags=["Enrichment"])
app.include_router(scoring_router, prefix=f"{settings.API_PREFIX}/scoring", tags=["Scoring"])
app.include_router(campaigns_router, prefix=f"{settings.API_PREFIX}/campaigns", tags=["Campaigns"])
app.include_router(webhooks_router, prefix=f"{settings.API_PREFIX}/webhooks", tags=["Webhooks"])
app.include_router(analytics_router, prefix=f"{settings.API_PREFIX}/analytics", tags=["Analytics"])
app.include_router(tracking_router, prefix=f"{settings.API_PREFIX}/track", tags=["Tracking"])


@app.get("/")
async def root():
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "running",
        "docs": "/docs",
    }


@app.get("/health")
async def health():
    return {"status": "healthy", "version": settings.APP_VERSION}
