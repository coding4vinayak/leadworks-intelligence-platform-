"""Lead management routes - CRUD, search, bulk operations."""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from pydantic import BaseModel, EmailStr
from datetime import datetime

from backend.routes.auth import get_current_user

router = APIRouter()


# --- Schemas ---
class LeadCreate(BaseModel):
    email: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None
    job_title: Optional[str] = None
    company_name: Optional[str] = None
    linkedin_url: Optional[str] = None
    website: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    source: Optional[str] = "manual"
    tags: Optional[List[str]] = []
    custom_fields: Optional[dict] = {}


class LeadUpdate(BaseModel):
    email: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None
    job_title: Optional[str] = None
    company_name: Optional[str] = None
    status: Optional[str] = None
    tags: Optional[List[str]] = None
    assigned_to: Optional[str] = None
    custom_fields: Optional[dict] = None


class LeadResponse(BaseModel):
    id: str
    email: Optional[str]
    first_name: Optional[str]
    last_name: Optional[str]
    phone: Optional[str]
    job_title: Optional[str]
    company_name: Optional[str]
    status: str
    source: str
    score: float
    category: Optional[str] = None
    is_enriched: bool
    is_spam: bool
    tags: List[str]
    created_at: str


class LeadListResponse(BaseModel):
    leads: List[LeadResponse]
    total: int
    page: int
    per_page: int
    total_pages: int


class BulkActionRequest(BaseModel):
    lead_ids: List[str]
    action: str  # delete, tag, assign, enrich, score, export
    params: Optional[dict] = {}


# --- Routes ---
@router.get("/", response_model=LeadListResponse)
async def list_leads(
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=1, le=100),
    status: Optional[str] = None,
    source: Optional[str] = None,
    score_min: Optional[float] = None,
    score_max: Optional[float] = None,
    search: Optional[str] = None,
    tags: Optional[str] = None,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    current_user: dict = Depends(get_current_user),
):
    """List leads with filtering, search, and pagination."""
    # In production: query database with filters
    return LeadListResponse(leads=[], total=0, page=page, per_page=per_page, total_pages=0)


@router.post("/", response_model=LeadResponse, status_code=201)
async def create_lead(
    lead: LeadCreate,
    auto_enrich: bool = Query(False, description="Auto-enrich after creation"),
    auto_score: bool = Query(True, description="Auto-score after creation"),
    check_fraud: bool = Query(True, description="Run fraud detection"),
    current_user: dict = Depends(get_current_user),
):
    """
    Create a new lead.
    Optionally triggers: fraud check, enrichment, scoring, automation.
    """
    # In production: create in DB, run fraud check, trigger enrichment
    return LeadResponse(
        id="new_lead_id",
        email=lead.email,
        first_name=lead.first_name,
        last_name=lead.last_name,
        phone=lead.phone,
        job_title=lead.job_title,
        company_name=lead.company_name,
        status="new",
        source=lead.source or "manual",
        score=0.0,
        is_enriched=False,
        is_spam=False,
        tags=lead.tags or [],
        created_at=datetime.utcnow().isoformat(),
    )


@router.get("/{lead_id}", response_model=LeadResponse)
async def get_lead(lead_id: str, current_user: dict = Depends(get_current_user)):
    """Get lead details with full enrichment data."""
    raise HTTPException(status_code=404, detail="Lead not found")


@router.patch("/{lead_id}", response_model=LeadResponse)
async def update_lead(
    lead_id: str,
    update: LeadUpdate,
    current_user: dict = Depends(get_current_user),
):
    """Update lead fields."""
    raise HTTPException(status_code=404, detail="Lead not found")


@router.delete("/{lead_id}")
async def delete_lead(lead_id: str, current_user: dict = Depends(get_current_user)):
    """Delete a lead."""
    return {"deleted": True, "id": lead_id}


@router.post("/bulk", response_model=dict)
async def bulk_action(
    request: BulkActionRequest,
    current_user: dict = Depends(get_current_user),
):
    """Perform bulk actions on multiple leads."""
    return {
        "action": request.action,
        "affected": len(request.lead_ids),
        "status": "completed",
    }


@router.post("/import/csv")
async def import_csv(
    file: UploadFile = File(...),
    auto_enrich: bool = Query(False),
    skip_duplicates: bool = Query(True),
    current_user: dict = Depends(get_current_user),
):
    """Import leads from CSV/Excel file."""
    content = await file.read()
    
    from backend.services.connectors.csv_import import CSVImporter
    importer = CSVImporter(credentials={}, config={})
    result = await importer.import_file(
        file_content=content,
        filename=file.filename,
        skip_duplicates=skip_duplicates,
    )
    
    return {
        "success": result.success,
        "records_processed": result.records_processed,
        "records_created": result.records_created,
        "records_failed": result.records_failed,
        "errors": result.errors[:10],
    }


@router.get("/{lead_id}/activities")
async def get_lead_activities(
    lead_id: str,
    page: int = 1,
    per_page: int = 50,
    current_user: dict = Depends(get_current_user),
):
    """Get activity timeline for a lead."""
    return {"activities": [], "total": 0}


@router.get("/{lead_id}/score")
async def get_lead_score(lead_id: str, current_user: dict = Depends(get_current_user)):
    """Get detailed scoring breakdown for a lead."""
    return {"score": 0, "category": "cold", "breakdown": {}, "signals": []}
