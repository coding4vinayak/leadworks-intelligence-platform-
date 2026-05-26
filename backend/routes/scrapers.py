"""Scraper routes - trigger and manage scraping jobs."""
from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from backend.routes.auth import get_current_user
from backend.services.scrapers import ScraperManager

router = APIRouter()


class ScrapeRequest(BaseModel):
    job_type: str  # website, linkedin_search, google_maps, email_finder, tech_stack
    params: dict = {}
    priority: int = 5


class LinkedInSearchRequest(BaseModel):
    query: Optional[str] = None
    job_title: Optional[str] = None
    location: Optional[str] = None
    industry: Optional[str] = None
    company: Optional[str] = None
    max_results: int = 25


class GoogleMapsSearchRequest(BaseModel):
    query: str
    location: Optional[str] = None
    max_results: int = 50
    min_rating: Optional[float] = None


class EmailFinderRequest(BaseModel):
    first_name: str
    last_name: str
    domain: Optional[str] = None
    company_name: Optional[str] = None
    verify: bool = True


class WebsiteScrapeRequest(BaseModel):
    url: str
    depth: int = 2
    max_pages: int = 20
    extract_emails: bool = True
    extract_phones: bool = True
    extract_social: bool = True


class TechStackRequest(BaseModel):
    domain: str
    deep_scan: bool = False


class FindLeadsRequest(BaseModel):
    query: str
    sources: Optional[List[str]] = None
    location: Optional[str] = None
    max_per_source: int = 25


@router.post("/run")
async def run_scrape_job(
    request: ScrapeRequest,
    current_user: dict = Depends(get_current_user),
):
    """Run a generic scraping job."""
    manager = ScraperManager()
    result = await manager.run_job(
        job_type=request.job_type,
        params=request.params,
        priority=request.priority,
    )
    return {
        "success": result.success,
        "records_found": result.records_found,
        "data": result.data[:50],
        "duration_seconds": result.duration_seconds,
        "errors": result.errors,
    }


@router.post("/linkedin/search")
async def search_linkedin(
    request: LinkedInSearchRequest,
    current_user: dict = Depends(get_current_user),
):
    """Search LinkedIn for leads by title, location, company."""
    manager = ScraperManager()
    result = await manager.run_job(
        job_type="linkedin_search",
        params={
            "query": request.query,
            "job_title": request.job_title,
            "location": request.location,
            "industry": request.industry,
            "max_results": request.max_results,
        },
    )
    return {
        "success": result.success,
        "profiles": result.data,
        "count": result.records_found,
    }


@router.post("/google-maps/search")
async def search_google_maps(
    request: GoogleMapsSearchRequest,
    current_user: dict = Depends(get_current_user),
):
    """Search Google Maps for businesses."""
    manager = ScraperManager()
    result = await manager.run_job(
        job_type="google_maps",
        params={
            "query": request.query,
            "location": request.location,
            "max_results": request.max_results,
            "min_rating": request.min_rating,
        },
    )
    return {
        "success": result.success,
        "businesses": result.data,
        "count": result.records_found,
    }


@router.post("/email/find")
async def find_email(
    request: EmailFinderRequest,
    current_user: dict = Depends(get_current_user),
):
    """Find email address for a person."""
    manager = ScraperManager()
    result = await manager.run_job(
        job_type="email_finder",
        params={
            "first_name": request.first_name,
            "last_name": request.last_name,
            "domain": request.domain,
            "company_name": request.company_name,
            "verify": request.verify,
        },
    )
    return {
        "success": result.success,
        "emails": result.data,
        "count": result.records_found,
        "metadata": result.metadata,
    }


@router.post("/website/scrape")
async def scrape_website(
    request: WebsiteScrapeRequest,
    current_user: dict = Depends(get_current_user),
):
    """Scrape a website for contact information."""
    manager = ScraperManager()
    result = await manager.run_job(
        job_type="website",
        params={
            "url": request.url,
            "depth": request.depth,
            "max_pages": request.max_pages,
            "extract_emails": request.extract_emails,
            "extract_phones": request.extract_phones,
            "extract_social": request.extract_social,
        },
    )
    return {
        "success": result.success,
        "data": result.data,
        "records_found": result.records_found,
    }


@router.post("/tech-stack")
async def detect_tech_stack(
    request: TechStackRequest,
    current_user: dict = Depends(get_current_user),
):
    """Detect technology stack of a domain."""
    manager = ScraperManager()
    result = await manager.run_job(
        job_type="tech_stack",
        params={"domain": request.domain, "deep_scan": request.deep_scan},
    )
    return {
        "success": result.success,
        "technologies": result.data[0] if result.data else {},
    }


@router.post("/find-leads")
async def find_leads(
    request: FindLeadsRequest,
    current_user: dict = Depends(get_current_user),
):
    """Find leads from multiple sources at once."""
    manager = ScraperManager()
    results = await manager.find_leads(
        query=request.query,
        sources=request.sources,
        location=request.location,
        max_per_source=request.max_per_source,
    )
    
    combined = {}
    for source, result in results.items():
        combined[source] = {
            "success": result.success,
            "count": result.records_found,
            "leads": manager.results_to_leads(result, source),
        }
    
    return {"results": combined}
