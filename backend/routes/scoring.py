"""Scoring routes - lead scoring and model management."""
from typing import List, Optional
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from backend.routes.auth import get_current_user
from backend.services.scoring import ScoringEngine

router = APIRouter()


class ScoreLeadRequest(BaseModel):
    lead_data: dict
    mode: str = "hybrid"  # weighted, ml, hybrid


class ScoreBatchRequest(BaseModel):
    lead_ids: List[str]
    mode: str = "hybrid"


class UpdateICPRequest(BaseModel):
    industries: Optional[List[str]] = None
    company_sizes: Optional[List[str]] = None
    job_titles: Optional[List[str]] = None
    tech_stack: Optional[List[str]] = None
    locations: Optional[List[str]] = None


class TrainModelRequest(BaseModel):
    model_type: str = "xgboost"  # xgboost, random_forest, gradient_boosting


@router.post("/lead")
async def score_lead(
    request: ScoreLeadRequest,
    current_user: dict = Depends(get_current_user),
):
    """Score a single lead."""
    engine = ScoringEngine()
    result = engine.score_lead(request.lead_data, mode=request.mode)
    return result


@router.post("/batch")
async def score_batch(
    request: ScoreBatchRequest,
    current_user: dict = Depends(get_current_user),
):
    """Score multiple leads."""
    return {
        "status": "queued",
        "leads_queued": len(request.lead_ids),
        "mode": request.mode,
    }


@router.post("/icp")
async def update_icp(
    request: UpdateICPRequest,
    current_user: dict = Depends(get_current_user),
):
    """Update Ideal Customer Profile for scoring."""
    icp = {
        "industries": request.industries or [],
        "company_sizes": request.company_sizes or [],
        "job_titles": request.job_titles or [],
        "tech_stack": request.tech_stack or [],
        "locations": request.locations or [],
    }
    return {"success": True, "icp": icp}


@router.post("/train")
async def train_model(
    request: TrainModelRequest,
    current_user: dict = Depends(get_current_user),
):
    """Train ML scoring model on historical data."""
    return {
        "status": "training_queued",
        "model_type": request.model_type,
        "message": "Model training started. This may take a few minutes.",
    }


@router.get("/model/status")
async def model_status(current_user: dict = Depends(get_current_user)):
    """Get current ML model status and metrics."""
    return {
        "model_type": "xgboost",
        "version": "1.0",
        "accuracy": 0.0,
        "is_trained": False,
        "last_trained": None,
        "feature_importances": {},
    }
