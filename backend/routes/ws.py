"""WebSocket routes for real-time updates."""
from typing import Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from backend.services.realtime.websocket_manager import ws_manager

router = APIRouter()


@router.websocket("/live")
async def websocket_endpoint(
    websocket: WebSocket,
    token: Optional[str] = Query(None),
    team_id: str = Query("default_team"),
    user_id: str = Query("default_user"),
):
    """
    WebSocket endpoint for real-time lead updates.

    Connect: ws://localhost:8000/api/v1/ws/live?token=xxx&team_id=xxx&user_id=xxx

    Events received:
    - lead.created, lead.updated, lead.scored, lead.enriched
    - email.opened, email.replied, visitor.active
    - scrape.completed, enrichment.completed
    - notification, stats.updated
    - import.progress, import.completed

    Client can send:
    - {"type": "subscribe", "events": ["lead.created", "lead.scored"]}
    - {"type": "ping"}
    """
    # TODO: Validate token in production
    await ws_manager.connect(websocket, team_id=team_id, user_id=user_id)

    try:
        while True:
            # Listen for client messages
            data = await websocket.receive_json()
            msg_type = data.get("type", "")

            if msg_type == "ping":
                await websocket.send_json({"type": "pong", "timestamp": ""})
            elif msg_type == "subscribe":
                # Update subscriptions
                events = data.get("events", ["*"])
                meta = ws_manager._connection_meta.get(websocket, {})
                meta["subscriptions"] = events

    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception:
        ws_manager.disconnect(websocket)


@router.get("/stats")
async def ws_stats():
    """Get WebSocket connection statistics."""
    return ws_manager.get_stats()
