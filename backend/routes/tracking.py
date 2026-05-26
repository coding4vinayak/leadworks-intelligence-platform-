"""Tracking routes - receive events from JS snippet, serve real-time data."""
from typing import Optional, Dict, Any, List
from fastapi import APIRouter, Request
from pydantic import BaseModel

from backend.services.tracking.tracker import LeadTracker
from backend.services.tracking.js_snippet import generate_tracking_snippet

router = APIRouter()

# Global tracker instance (in production: use Redis-backed tracker)
tracker = LeadTracker()


class TrackEventRequest(BaseModel):
    team_id: str
    visitor_id: str
    session_id: str
    event_type: str
    url: Optional[str] = None
    page_title: Optional[str] = None
    referrer: Optional[str] = None
    timestamp: Optional[str] = None
    properties: Dict[str, Any] = {}
    utm: Optional[Dict[str, str]] = None
    screen: Optional[Dict[str, int]] = None
    timezone: Optional[str] = None


class IdentifyRequest(BaseModel):
    visitor_id: str
    email: str
    lead_id: Optional[str] = None
    properties: Dict[str, Any] = {}


@router.post("/event")
async def track_event(request: Request, body: TrackEventRequest):
    """
    Receive tracking events from the JS snippet.
    No auth required - uses team_id for routing.
    """
    ip = request.client.host if request.client else None
    ua = request.headers.get("user-agent", "")

    if body.event_type == "page_view":
        result = tracker.track_page_view(
            visitor_id=body.visitor_id,
            url=body.url or "",
            page_title=body.page_title,
            referrer=body.referrer,
            ip_address=ip,
            user_agent=ua,
            utm_params=body.utm,
        )
    elif body.event_type == "identify":
        email = body.properties.get("email", "")
        lead_id = body.properties.get("lead_id", body.visitor_id)
        result = tracker.identify_visitor(
            visitor_id=body.visitor_id,
            lead_id=lead_id,
            email=email,
        )
    else:
        result = tracker.track_event(
            visitor_id=body.visitor_id,
            event_type=body.event_type,
            properties=body.properties,
            url=body.url,
            ip_address=ip,
            user_agent=ua,
        )

    return {"ok": True, **result}


@router.post("/identify")
async def identify_visitor(body: IdentifyRequest):
    """Link an anonymous visitor to a known lead/email."""
    lead_id = body.lead_id or body.email  # Use email as fallback ID
    result = tracker.identify_visitor(
        visitor_id=body.visitor_id,
        lead_id=lead_id,
        email=body.email,
    )
    return result


@router.get("/visitors/active")
async def get_active_visitors():
    """Get currently active visitors (real-time dashboard)."""
    visitors = tracker.get_active_visitors()
    return {"active_visitors": visitors, "count": len(visitors)}


@router.get("/visitor/{visitor_id}/history")
async def get_visitor_history(visitor_id: str):
    """Get full browsing history for a visitor."""
    history = tracker.get_visitor_history(visitor_id)
    return history


@router.get("/lead/{lead_id}/activity")
async def get_lead_tracking(lead_id: str):
    """Get all tracking data for a specific lead."""
    activity = tracker.get_lead_activity(lead_id)
    return activity


@router.get("/snippet")
async def get_tracking_snippet(team_id: str, api_url: str = "https://api.leadworks.io"):
    """Get the JS tracking snippet to embed on customer websites."""
    snippet = generate_tracking_snippet(team_id, api_url)
    return {"snippet": snippet, "team_id": team_id}


@router.get("/snippet.js")
async def serve_tracking_script(team_id: str):
    """Serve the tracking script directly as JS (for <script src="..."> embedding)."""
    from fastapi.responses import Response
    snippet = generate_tracking_snippet(team_id)
    # Strip the <script> tags for direct JS serving
    js_content = snippet.replace("<!-- Leadworks Tracking Snippet -->\n<script>\n", "")
    js_content = js_content.replace("\n</script>", "")
    return Response(content=js_content, media_type="application/javascript")
