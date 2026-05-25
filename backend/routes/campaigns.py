"""Campaign and automation routes."""
from typing import List, Optional
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from backend.routes.auth import get_current_user

router = APIRouter()


class CampaignCreate(BaseModel):
    name: str
    campaign_type: str = "drip"
    target_segment: Optional[dict] = {}
    steps: List[dict] = []
    send_window_start: str = "09:00"
    send_window_end: str = "17:00"
    timezone: str = "UTC"


class CampaignUpdate(BaseModel):
    name: Optional[str] = None
    status: Optional[str] = None
    steps: Optional[List[dict]] = None


class WorkflowTriggerRequest(BaseModel):
    workflow_id: str
    lead_id: str


@router.get("/")
async def list_campaigns(
    status: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
):
    """List all campaigns."""
    return {"campaigns": [], "total": 0}


@router.post("/", status_code=201)
async def create_campaign(
    request: CampaignCreate,
    current_user: dict = Depends(get_current_user),
):
    """Create a new campaign/automation."""
    return {
        "id": "campaign_new_id",
        "name": request.name,
        "type": request.campaign_type,
        "status": "draft",
        "steps": len(request.steps),
    }


@router.get("/{campaign_id}")
async def get_campaign(campaign_id: str, current_user: dict = Depends(get_current_user)):
    """Get campaign details with metrics."""
    return {"id": campaign_id, "status": "draft"}


@router.patch("/{campaign_id}")
async def update_campaign(
    campaign_id: str,
    request: CampaignUpdate,
    current_user: dict = Depends(get_current_user),
):
    """Update campaign settings."""
    return {"id": campaign_id, "updated": True}


@router.post("/{campaign_id}/activate")
async def activate_campaign(campaign_id: str, current_user: dict = Depends(get_current_user)):
    """Activate a campaign to start processing."""
    return {"id": campaign_id, "status": "active"}


@router.post("/{campaign_id}/pause")
async def pause_campaign(campaign_id: str, current_user: dict = Depends(get_current_user)):
    """Pause an active campaign."""
    return {"id": campaign_id, "status": "paused"}


@router.get("/{campaign_id}/metrics")
async def campaign_metrics(campaign_id: str, current_user: dict = Depends(get_current_user)):
    """Get campaign performance metrics."""
    return {
        "enrolled": 0, "active": 0, "completed": 0,
        "emails_sent": 0, "opened": 0, "clicked": 0,
        "replied": 0, "converted": 0, "conversion_rate": 0.0,
    }


@router.get("/workflows/templates")
async def list_workflow_templates(current_user: dict = Depends(get_current_user)):
    """List pre-built workflow templates."""
    from backend.services.automation import WorkflowEngine
    engine = WorkflowEngine()
    return {"templates": engine.get_default_workflows()}


@router.post("/workflows/trigger")
async def trigger_workflow(
    request: WorkflowTriggerRequest,
    current_user: dict = Depends(get_current_user),
):
    """Manually trigger a workflow for a lead."""
    return {"status": "triggered", "workflow_id": request.workflow_id}
