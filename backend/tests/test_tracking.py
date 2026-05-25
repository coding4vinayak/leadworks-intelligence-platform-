"""Tests for real-time tracking engine."""
import pytest
from backend.services.tracking.tracker import LeadTracker


class TestLeadTracker:
    """Test visitor and lead tracking."""

    def setup_method(self):
        self.tracker = LeadTracker()

    def test_track_page_view(self):
        """Basic page view tracking."""
        result = self.tracker.track_page_view(
            visitor_id="visitor_1",
            url="https://example.com/pricing",
            page_title="Pricing - Example",
        )
        assert result["session_id"] is not None
        assert result["page_views"] == 1
        assert "visited_pricing" in result["intent_signals"]

    def test_session_continuity(self):
        """Multiple page views in same session."""
        self.tracker.track_page_view(visitor_id="v1", url="https://example.com/")
        result = self.tracker.track_page_view(visitor_id="v1", url="https://example.com/about")
        assert result["page_views"] == 2

    def test_intent_detection(self):
        """Should detect buying intent from URLs."""
        self.tracker.track_page_view(visitor_id="v1", url="https://example.com/pricing")
        self.tracker.track_page_view(visitor_id="v1", url="https://example.com/demo")

        history = self.tracker.get_visitor_history("v1")
        assert "visited_pricing" in history["intent_signals"]
        assert "visited_demo" in history["intent_signals"]

    def test_custom_event_tracking(self):
        """Track custom events."""
        result = self.tracker.track_event(
            visitor_id="v1",
            event_type="form_submit",
            properties={"form_id": "contact_form"},
        )
        assert result["is_high_intent"] is True
        assert result["should_rescore"] is True

    def test_identify_visitor(self):
        """Link anonymous visitor to a lead."""
        # Track some anonymous activity
        self.tracker.track_page_view(visitor_id="v1", url="https://example.com/pricing")
        self.tracker.track_page_view(visitor_id="v1", url="https://example.com/demo")

        # Identify
        result = self.tracker.identify_visitor(
            visitor_id="v1",
            lead_id="lead_123",
            email="john@company.com",
        )
        assert result["lead_id"] == "lead_123"
        assert result["should_enrich"] is True
        assert result["history"]["total_page_views"] == 2

    def test_get_lead_activity(self):
        """Get all tracking data for a lead."""
        self.tracker.track_page_view(visitor_id="v1", url="https://example.com/")
        self.tracker.identify_visitor(visitor_id="v1", lead_id="lead_1")
        self.tracker.track_page_view(visitor_id="v1", url="https://example.com/pricing")

        activity = self.tracker.get_lead_activity("lead_1")
        assert activity["has_tracking_data"] is True
        assert activity["total_page_views"] >= 2

    def test_active_visitors(self):
        """Get currently active visitors."""
        self.tracker.track_page_view(visitor_id="v1", url="https://example.com/")
        self.tracker.track_page_view(visitor_id="v2", url="https://example.com/pricing")

        active = self.tracker.get_active_visitors()
        assert len(active) == 2

    def test_device_detection(self):
        """Detect device type from user agent."""
        self.tracker.track_page_view(
            visitor_id="mobile_user",
            url="https://example.com/",
            user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)",
        )
        history = self.tracker.get_visitor_history("mobile_user")
        assert history["device_type"] == "mobile"

    def test_utm_capture(self):
        """Capture UTM parameters."""
        self.tracker.track_page_view(
            visitor_id="v1",
            url="https://example.com/?utm_source=google",
            utm_params={"utm_source": "google", "utm_medium": "cpc", "utm_campaign": "brand"},
        )
        history = self.tracker.get_visitor_history("v1")
        assert history["utm_source"] == "google"
        assert history["utm_medium"] == "cpc"

    def test_high_engagement_signal(self):
        """5+ page views should trigger high engagement signal."""
        for i in range(6):
            self.tracker.track_page_view(visitor_id="v1", url=f"https://example.com/page{i}")

        history = self.tracker.get_visitor_history("v1")
        assert "high_page_count" in history["intent_signals"]
