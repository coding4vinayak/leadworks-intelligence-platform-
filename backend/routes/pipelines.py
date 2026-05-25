"""Pipeline routes - manage and run data pipelines."""
from typing import List, Optional
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from backend.routes.auth import get_current_user
from backend.services.pipelines import PipelineEngine

router = APIRouter()
pipeline_engine = PipelineEngine()


class CreatePipelineRequest(BaseModel):
    name: str
    steps: List[dict]
    description: str = ""
    trigger: str = "manual"
    trigger_config: Optional[dict] = None


class RunPipelineRequest(BaseModel):
    input_data: List[dict]
    dry_run: bool = False


@router.get("/")
async def list_pipelines(current_user: dict = Depends(get_current_user)):
    """List all pipelines."""
    team_id = current_user.get("team_id")
    return {"pipelines": pipeline_engine.list_pipelines(team_id)}


@router.get("/templates")
async def get_pipeline_templates(current_user: dict = Depends(get_current_user)):
    """Get pre-built pipeline templates."""
    return {"templates": pipeline_engine.get_templates()}


@router.post("/", status_code=201)
async def create_pipeline(
    request: CreatePipelineRequest,
    current_user: dict = Depends(get_current_user),
):
    """Create a new data pipeline."""
    team_id = current_user.get("team_id")
    pipeline = pipeline_engine.create_pipeline(
        name=request.name,
        steps=request.steps,
        description=request.description,
        trigger=request.trigger,
        trigger_config=request.trigger_config,
        team_id=team_id,
    )
    return {
        "id": pipeline.id,
        "name": pipeline.name,
        "steps_count": len(pipeline.steps),
    }


@router.post("/{pipeline_id}/run")
async def run_pipeline(
    pipeline_id: str,
    request: RunPipelineRequest,
    current_user: dict = Depends(get_current_user),
):
    """Execute a pipeline on input data."""
    run = await pipeline_engine.run_pipeline(
        pipeline_id=pipeline_id,
        input_data=request.input_data,
        dry_run=request.dry_run,
    )
    return pipeline_engine.get_run_status(run.id)


@router.get("/{pipeline_id}")
async def get_pipeline(pipeline_id: str, current_user: dict = Depends(get_current_user)):
    """Get pipeline details."""
    pipeline = pipeline_engine.pipelines.get(pipeline_id)
    if not pipeline:
        return {"error": "Pipeline not found"}
    return {
        "id": pipeline.id,
        "name": pipeline.name,
        "description": pipeline.description,
        "steps": [
            {"id": s.id, "type": s.step_type.value, "name": s.name, "config": s.config}
            for s in pipeline.steps
        ],
        "trigger": pipeline.trigger,
        "is_active": pipeline.is_active,
        "total_runs": pipeline.total_runs,
    }


@router.get("/runs/{run_id}")
async def get_run_status(run_id: str, current_user: dict = Depends(get_current_user)):
    """Get pipeline run status and results."""
    status = pipeline_engine.get_run_status(run_id)
    if not status:
        return {"error": "Run not found"}
    return status


@router.post("/{pipeline_id}/activate")
async def activate_pipeline(pipeline_id: str, current_user: dict = Depends(get_current_user)):
    """Activate a pipeline for scheduled/event execution."""
    pipeline = pipeline_engine.pipelines.get(pipeline_id)
    if pipeline:
        pipeline.is_active = True
        return {"activated": True, "id": pipeline_id}
    return {"error": "Pipeline not found"}


@router.post("/{pipeline_id}/deactivate")
async def deactivate_pipeline(pipeline_id: str, current_user: dict = Depends(get_current_user)):
    """Deactivate a pipeline."""
    pipeline = pipeline_engine.pipelines.get(pipeline_id)
    if pipeline:
        pipeline.is_active = False
        return {"deactivated": True, "id": pipeline_id}
    return {"error": "Pipeline not found"}
