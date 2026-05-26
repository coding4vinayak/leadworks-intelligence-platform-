"""Real-time lead activity tracker with session management."""
import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from uuid import uuid4
import structlog

logger = structlog.get_logger()


@dataclass
class TrackingEvent:
    """A single tracking event."""
    event_type: str  # page_view, click, form_submit, scroll_depth, etc.
    timestamp: datetime
    url: Optional[str] = None
    page_title: Optional[str] = None
    referrer: Optional[str] = None
    properties: Dict[str, Any] = field(default_factory=dict)
    session_id: Optional[str] = None
    visitor_id: Optional[str] = None
    lead_id: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    duration_seconds: Optional[float] = None


@dataclass
class VisitorSession:
    """Tracks a visitor's browsing session."""
    session_id: str
    visitor_id: str
    lead_id: Optional[str] = None
    started_at: datetime = field(default_factory=datetime.utcnow)
    last_activity_at: datetime = field(default_factory=datetime.utcnow)
    page_views: int = 0
    events: List[TrackingEvent] = field(default_factory=list)
    pages_visited: List[str] = field(default_factory=list)
    total_time_seconds: float = 0.0
    utm_source: Optional[str] = None
    utm_medium: Optional[str] = None
    utm_campaign: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    country: Optional[str] = None
    city: Optional[str] = None
    device_type: Optional[str] = None  # desktop, mobile, tablet


class LeadTracker:
    """
    Real-time visitor and lead tracking engine.

    Features:
    - Anonymous visitor tracking (cookie-based)
    - Session management with auto-expiry
    - Page view tracking with time-on-page
    - Custom event tracking (clicks, form fills, downloads)
    - UTM parameter capture
    - Visitor-to-lead identification (form submit, login)
    - Intent signal detection (pricing page, demo page, etc.)
    - Scroll depth tracking
    - Device/geo detection
    - Real-time scoring trigger on key events
    """

    # Pages that indicate buying intent
    INTENT_PAGES = {
        "/pricing": "visited_pricing",
        "/demo": "visited_demo",
        "/trial": "visited_trial",
        "/signup": "visited_signup",
        "/contact": "visited_contact",
        "/case-study": "visited_case_study",
        "/case-studies": "visited_case_study",
        "/customers": "visited_customers",
        "/enterprise": "visited_enterprise",
        "/book-demo": "visited_demo",
        "/request-demo": "visited_demo",
        "/free-trial": "visited_trial",
        "/get-started": "visited_signup",
        "/comparison": "visited_comparison",
        "/vs-": "visited_comparison",
        "/roi": "visited_roi",
        "/integrations": "visited_integrations",
    }

    # Events that indicate strong intent
    HIGH_INTENT_EVENTS = {
        "form_submit", "demo_request", "trial_start",
        "pricing_toggle", "plan_select", "chat_initiated",
        "calendar_booked", "proposal_viewed", "contract_viewed",
    }

    def __init__(self):
        # In production: use Redis for session storage
        self._sessions: Dict[str, VisitorSession] = {}
        self._visitor_lead_map: Dict[str, str] = {}  # visitor_id -> lead_id
        self._session_timeout = timedelta(minutes=30)

    def generate_visitor_id(self, ip: str, user_agent: str) -> str:
        """Generate a deterministic visitor ID from IP + UA for anonymous tracking."""
        raw = f"{ip}:{user_agent}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    def get_or_create_session(
        self,
        visitor_id: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> VisitorSession:
        """Get existing session or create a new one."""
        # Check for active session
        for session in self._sessions.values():
            if session.visitor_id == visitor_id:
                if datetime.utcnow() - session.last_activity_at < self._session_timeout:
                    session.last_activity_at = datetime.utcnow()
                    return session

        # Create new session
        session = VisitorSession(
            session_id=str(uuid4()),
            visitor_id=visitor_id,
            lead_id=self._visitor_lead_map.get(visitor_id),
            ip_address=ip_address,
            user_agent=user_agent,
            device_type=self._detect_device(user_agent or ""),
        )
        self._sessions[session.session_id] = session
        return session

    def track_page_view(
        self,
        visitor_id: str,
        url: str,
        page_title: Optional[str] = None,
        referrer: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        utm_params: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        Track a page view event.

        Returns intent signals detected from this page view.
        """
        session = self.get_or_create_session(visitor_id, ip_address, user_agent)

        event = TrackingEvent(
            event_type="page_view",
            timestamp=datetime.utcnow(),
            url=url,
            page_title=page_title,
            referrer=referrer,
            session_id=session.session_id,
            visitor_id=visitor_id,
            lead_id=session.lead_id,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        session.events.append(event)
        session.page_views += 1
        session.pages_visited.append(url)

        # Capture UTM params
        if utm_params:
            session.utm_source = utm_params.get("utm_source")
            session.utm_medium = utm_params.get("utm_medium")
            session.utm_campaign = utm_params.get("utm_campaign")

        # Detect intent signals
        signals = self._detect_intent_signals(url, session)

        result = {
            "session_id": session.session_id,
            "page_views": session.page_views,
            "intent_signals": signals,
            "is_return_visitor": session.page_views > 1,
        }

        # Trigger scoring if high-intent page visited
        if signals:
            result["should_rescore"] = True
            logger.info(
                "intent_signal_detected",
                visitor_id=visitor_id,
                lead_id=session.lead_id,
                signals=signals,
                url=url,
            )

        return result

    def track_event(
        self,
        visitor_id: str,
        event_type: str,
        properties: Optional[Dict[str, Any]] = None,
        url: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Track a custom event (click, form submit, download, etc.).
        """
        session = self.get_or_create_session(visitor_id, ip_address, user_agent)

        event = TrackingEvent(
            event_type=event_type,
            timestamp=datetime.utcnow(),
            url=url,
            properties=properties or {},
            session_id=session.session_id,
            visitor_id=visitor_id,
            lead_id=session.lead_id,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        session.events.append(event)

        result = {
            "session_id": session.session_id,
            "event_type": event_type,
            "is_high_intent": event_type in self.HIGH_INTENT_EVENTS,
        }

        if event_type in self.HIGH_INTENT_EVENTS:
            result["should_rescore"] = True
            result["should_notify"] = True

        return result

    def identify_visitor(
        self,
        visitor_id: str,
        lead_id: str,
        email: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Link an anonymous visitor to a known lead.
        Called when visitor fills a form, logs in, or clicks tracked email.
        """
        self._visitor_lead_map[visitor_id] = lead_id

        # Update all sessions for this visitor
        for session in self._sessions.values():
            if session.visitor_id == visitor_id:
                session.lead_id = lead_id

        # Get full visitor history
        history = self.get_visitor_history(visitor_id)

        logger.info(
            "visitor_identified",
            visitor_id=visitor_id,
            lead_id=lead_id,
            email=email,
            total_page_views=history["total_page_views"],
            sessions=history["total_sessions"],
        )

        return {
            "lead_id": lead_id,
            "visitor_id": visitor_id,
            "history": history,
            "should_enrich": True,
            "should_rescore": True,
        }

    def get_visitor_history(self, visitor_id: str) -> Dict[str, Any]:
        """Get complete browsing history for a visitor."""
        sessions = [s for s in self._sessions.values() if s.visitor_id == visitor_id]

        all_pages = []
        all_events = []
        total_time = 0.0

        for session in sessions:
            all_pages.extend(session.pages_visited)
            all_events.extend(session.events)
            total_time += session.total_time_seconds

        # Detect all intent signals
        all_signals = set()
        for page in all_pages:
            for pattern, signal in self.INTENT_PAGES.items():
                if pattern in page.lower():
                    all_signals.add(signal)

        for event in all_events:
            if event.event_type in self.HIGH_INTENT_EVENTS:
                all_signals.add(f"event:{event.event_type}")

        return {
            "visitor_id": visitor_id,
            "lead_id": self._visitor_lead_map.get(visitor_id),
            "total_sessions": len(sessions),
            "total_page_views": sum(s.page_views for s in sessions),
            "total_events": len(all_events),
            "total_time_minutes": round(total_time / 60, 1),
            "pages_visited": list(set(all_pages)),
            "intent_signals": list(all_signals),
            "first_seen": min(s.started_at for s in sessions).isoformat() if sessions else None,
            "last_seen": max(s.last_activity_at for s in sessions).isoformat() if sessions else None,
            "utm_source": sessions[-1].utm_source if sessions else None,
            "utm_medium": sessions[-1].utm_medium if sessions else None,
            "utm_campaign": sessions[-1].utm_campaign if sessions else None,
            "device_type": sessions[-1].device_type if sessions else None,
            "is_return_visitor": len(sessions) > 1,
        }

    def get_lead_activity(self, lead_id: str) -> Dict[str, Any]:
        """Get all tracking data for a specific lead."""
        visitor_ids = [vid for vid, lid in self._visitor_lead_map.items() if lid == lead_id]

        if not visitor_ids:
            return {"lead_id": lead_id, "has_tracking_data": False}

        # Combine data from all visitor IDs (same person, different devices)
        combined = {
            "lead_id": lead_id,
            "has_tracking_data": True,
            "visitor_ids": visitor_ids,
            "sessions": [],
            "total_page_views": 0,
            "total_events": 0,
            "intent_signals": set(),
            "pages_visited": set(),
        }

        for vid in visitor_ids:
            history = self.get_visitor_history(vid)
            combined["total_page_views"] += history["total_page_views"]
            combined["total_events"] += history["total_events"]
            combined["intent_signals"].update(history["intent_signals"])
            combined["pages_visited"].update(history["pages_visited"])

        combined["intent_signals"] = list(combined["intent_signals"])
        combined["pages_visited"] = list(combined["pages_visited"])

        return combined

    def get_active_visitors(self) -> List[Dict[str, Any]]:
        """Get currently active visitors (for real-time dashboard)."""
        now = datetime.utcnow()
        active = []

        for session in self._sessions.values():
            if now - session.last_activity_at < self._session_timeout:
                active.append({
                    "visitor_id": session.visitor_id,
                    "lead_id": session.lead_id,
                    "session_id": session.session_id,
                    "current_page": session.pages_visited[-1] if session.pages_visited else None,
                    "page_views": session.page_views,
                    "time_on_site": (now - session.started_at).total_seconds(),
                    "device_type": session.device_type,
                    "country": session.country,
                })

        return active

    def _detect_intent_signals(self, url: str, session: VisitorSession) -> List[str]:
        """Detect buying intent signals from URL and session context."""
        signals = []
        url_lower = url.lower()

        for pattern, signal in self.INTENT_PAGES.items():
            if pattern in url_lower:
                signals.append(signal)

        # Multi-page visit signals
        if session.page_views >= 5:
            signals.append("high_page_count")
        if session.page_views >= 10:
            signals.append("very_high_engagement")

        # Return visitor signal
        visitor_sessions = [
            s for s in self._sessions.values()
            if s.visitor_id == session.visitor_id and s.session_id != session.session_id
        ]
        if visitor_sessions:
            signals.append("return_visitor")

        return signals

    def _detect_device(self, user_agent: str) -> str:
        """Simple device type detection from user agent."""
        ua_lower = user_agent.lower()
        if any(m in ua_lower for m in ["iphone", "android", "mobile"]):
            return "mobile"
        elif any(t in ua_lower for t in ["ipad", "tablet"]):
            return "tablet"
        return "desktop"
