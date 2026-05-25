"""Segmentation routes - manage dynamic segments."""
from typing import List, Optional
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from backend.routes.auth import get_current_user
from backend.services.segmentation import SegmentEngine

router = APIRouter()
segment_engine = SegmentEngine()


class SegmentRuleInput(BaseModel):
    field: str
    operator: str
    value: any = None


class CreateSegmentRequest(BaseModel):
    name: str
    rules: List[dict]
    logic: str = "and"
    description: str = ""


class SegmentSuggestRequest(BaseModel):
    leads: List[dict]


@router.get("/")
async def list_segments(current_user: dict = Depends(get_current_user)):
    """List all segments."""
    return {"segments": segment_engine.list_segments()}


@router.post("/", status_code=201)
async def create_segment(
    request: CreateSegmentRequest,
    current_user: dict = Depends(get_current_user),
):
    """Create a new dynamic segment."""
    segment = segment_engine.create_segment(
        name=request.name,
        rules=request.rules,
        logic=request.logic,
        description=request.description,
    )
    return {
        "id": segment.id,
        "name": segment.name,
        "rules_count": len(segment.rules),
    }


@router.get("/{segment_id}")
async def get_segment(segment_id: str, current_user: dict = Depends(get_current_user)):
    """Get segment details and analytics."""
    segment = segment_engine.segments.get(segment_id)
    if not segment:
        return {"error": "Segment not found"}
    return {
        "id": segment.id,
        "name": segment.name,
        "description": segment.description,
        "rules_count": len(segment.rules),
        "logic": segment.logic,
        "is_ai_generated": segment.is_ai_generated,
    }


@router.post("/{segment_id}/members")
async def get_segment_members(
    segment_id: str,
    leads: List[dict],
    current_user: dict = Depends(get_current_user),
):
    """Get leads matching a segment."""
    members = segment_engine.get_segment_members(segment_id, leads)
    return {"members": members, "count": len(members)}


@router.post("/evaluate")
async def evaluate_lead(
    lead: dict,
    current_user: dict = Depends(get_current_user),
):
    """Evaluate which segments a lead belongs to."""
    segments = segment_engine.evaluate_lead(lead)
    return {"segments": segments}


@router.post("/suggest")
async def suggest_segments(
    request: SegmentSuggestRequest,
    current_user: dict = Depends(get_current_user),
):
    """Get AI-powered segment suggestions based on lead data."""
    suggestions = segment_engine.suggest_segments(request.leads)
    return {"suggestions": suggestions}


@router.get("/{segment_id}/analytics")
async def segment_analytics(
    segment_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Get analytics for a segment."""
    # In production: fetch leads from DB
    return segment_engine.get_segment_analytics(segment_id, [])
