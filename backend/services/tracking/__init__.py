"""Real-time lead tracking - page visits, events, and behavioral data."""
from backend.services.tracking.tracker import LeadTracker, TrackingEvent
from backend.services.tracking.js_snippet import generate_tracking_snippet

__all__ = ["LeadTracker", "TrackingEvent", "generate_tracking_snippet"]
