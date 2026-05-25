"""Company routes - company intelligence and management."""
from typing import Optional
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from backend.routes.auth import get_current_user

router = APIRouter()


class CompanyCreate(BaseModel):
    name: str
    domain: Optional[str] = None
    industry: Optional[str] = None
    website: Optional[str] = None


@router.get("/")
async def list_companies(
    page: int = 1,
    per_page: int = 25,
    search: Optional[str] = None,
    industry: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
):
    """List companies with search and filters."""
    return {"companies": [], "total": 0}


@router.post("/", status_code=201)
async def create_company(
    request: CompanyCreate,
    current_user: dict = Depends(get_current_user),
):
    """Create a company record."""
    return {"id": "company_id", "name": request.name}


@router.get("/{company_id}")
async def get_company(company_id: str, current_user: dict = Depends(get_current_user)):
    """Get company details with tech stack, employees, etc."""
    return {"id": company_id}


@router.get("/{company_id}/leads")
async def get_company_leads(company_id: str, current_user: dict = Depends(get_current_user)):
    """Get all leads associated with a company."""
    return {"leads": [], "total": 0}


@router.post("/{company_id}/enrich")
async def enrich_company(company_id: str, current_user: dict = Depends(get_current_user)):
    """Enrich company with tech stack, funding, employee data."""
    return {"status": "enrichment_queued"}
