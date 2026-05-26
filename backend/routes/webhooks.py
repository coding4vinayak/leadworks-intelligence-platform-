"""Webhook routes - receive inbound webhooks and tracking events."""
from fastapi import APIRouter, Request, Header
from typing import Optional

router = APIRouter()


@router.post("/inbound/{connector_id}")
async def receive_webhook(
    connector_id: str,
    request: Request,
    x_webhook_signature: Optional[str] = Header(None),
):
    """
    Receive inbound webhook from any source (forms, Zapier, etc).
    No auth required - uses webhook signature for verification.
    """
    body = await request.json()
    source_ip = request.client.host if request.client else None

    from backend.services.connectors import ConnectorManager
    manager = ConnectorManager()
    result = await manager.process_webhook(
        connector_id=connector_id,
        payload=body,
        headers=dict(request.headers),
        source_ip=source_ip,
    )

    return {
        "success": result.success,
        "lead_created": result.records_created > 0,
    }


@router.get("/track/open/{message_id}")
async def track_email_open(message_id: str):
    """Track email open via invisible pixel."""
    # In production: log the open event, update lead engagement
    # Return 1x1 transparent pixel
    from fastapi.responses import Response
    pixel = b'\x47\x49\x46\x38\x39\x61\x01\x00\x01\x00\x00\x00\x00\x21\xf9\x04\x00\x00\x00\x00\x00\x2c\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x00\x3b'
    return Response(content=pixel, media_type="image/gif")


@router.get("/track/click/{message_id}")
async def track_email_click(message_id: str, url: str):
    """Track email click and redirect to original URL."""
    # In production: log the click event, update lead engagement
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url=url)


@router.get("/unsubscribe/{message_id}")
async def unsubscribe(message_id: str):
    """Handle email unsubscribe."""
    # In production: mark lead as unsubscribed, remove from campaigns
    return {"status": "unsubscribed", "message": "You have been unsubscribed."}
