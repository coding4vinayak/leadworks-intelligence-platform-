"""Connector routes - manage integrations."""
from typing import Optional
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from backend.routes.auth import get_current_user
from backend.services.connectors import ConnectorManager

router = APIRouter()
connector_manager = ConnectorManager()


class ConnectorCreate(BaseModel):
    connector_type: str
    name: str
    credentials: dict = {}
    config: dict = {}
    field_mapping: Optional[dict] = None


class ConnectorSyncRequest(BaseModel):
    direction: str = "inbound"


@router.get("/available")
async def list_available_connectors(current_user: dict = Depends(get_current_user)):
    """List all available connector types."""
    return {"connectors": connector_manager.get_available_connectors()}


@router.post("/")
async def create_connector(
    request: ConnectorCreate,
    current_user: dict = Depends(get_current_user),
):
    """Create and configure a new connector."""
    connector = connector_manager.create_connector(
        connector_type=request.connector_type,
        credentials=request.credentials,
        config=request.config,
        field_mapping=request.field_mapping,
        connector_id=f"{current_user['team_id']}_{request.connector_type}",
    )
    return {
        "success": True,
        "connector_type": request.connector_type,
        "name": request.name,
    }


@router.post("/{connector_id}/test")
async def test_connector(connector_id: str, current_user: dict = Depends(get_current_user)):
    """Test connector connection."""
    success = await connector_manager.test_connector(connector_id)
    return {"success": success, "connector_id": connector_id}


@router.post("/{connector_id}/sync")
async def sync_connector(
    connector_id: str,
    request: ConnectorSyncRequest,
    current_user: dict = Depends(get_current_user),
):
    """Trigger a sync operation."""
    result = await connector_manager.run_sync(
        connector_id=connector_id,
        direction=request.direction,
    )
    return {
        "success": result.success,
        "records_processed": result.records_processed,
        "records_created": result.records_created,
        "records_updated": result.records_updated,
        "errors": result.errors[:10],
    }
