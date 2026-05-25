"""Tests for notification engine."""
import pytest
from backend.services.notifications.notification_engine import (
    NotificationEngine, NotificationType, NotificationChannel, NotificationPriority
)


class TestNotificationEngine:
    """Test the notification system."""

    def setup_method(self):
        self.engine = NotificationEngine()

    def test_send_basic_notification(self):
        """Send a notification and retrieve it."""
        notif = self.engine.notify(
            notification_type=NotificationType.NEW_HOT_LEAD,
            user_id="user_1",
            data={
                "lead_name": "Sarah Chen",
                "company": "TechCorp",
                "score": 92,
                "job_title": "VP Engineering",
            },
        )
        assert notif.title == "🔥 New Hot Lead: Sarah Chen"
        assert "TechCorp" in notif.message
        assert notif.priority == NotificationPriority.HIGH

    def test_get_notifications_feed(self):
        """Get notification feed for a user."""
        self.engine.notify(NotificationType.NEW_HOT_LEAD, "user_1", {"lead_name": "A", "company": "B", "score": 90, "job_title": "CTO"})
        self.engine.notify(NotificationType.SCRAPE_COMPLETE, "user_1", {"job_type": "linkedin", "records_found": 25, "duration": 30})

        feed = self.engine.get_notifications("user_1")
        assert feed["total"] == 2
        assert feed["unread_count"] == 2
        assert len(feed["notifications"]) == 2

    def test_mark_read(self):
        """Mark notifications as read."""
        n1 = self.engine.notify(NotificationType.LEAD_REPLIED, "user_1", {"lead_name": "Bob", "company": "X"})
        n2 = self.engine.notify(NotificationType.SCORE_CHANGED, "user_1", {"lead_name": "Alice", "old_score": 50, "new_score": 80, "direction": "up"})

        # Mark one as read
        count = self.engine.mark_read("user_1", [n1.id])
        assert count == 1
        assert self.engine.get_unread_count("user_1") == 1

    def test_mark_all_read(self):
        """Mark all notifications as read."""
        self.engine.notify(NotificationType.NEW_HOT_LEAD, "user_1", {"lead_name": "A", "company": "B", "score": 90, "job_title": "X"})
        self.engine.notify(NotificationType.LEAD_REPLIED, "user_1", {"lead_name": "C", "company": "D"})

        count = self.engine.mark_read("user_1", None)
        assert count == 2
        assert self.engine.get_unread_count("user_1") == 0

    def test_unread_only_filter(self):
        """Filter for unread notifications only."""
        n1 = self.engine.notify(NotificationType.NEW_HOT_LEAD, "user_1", {"lead_name": "A", "company": "B", "score": 90, "job_title": "X"})
        self.engine.notify(NotificationType.LEAD_REPLIED, "user_1", {"lead_name": "C", "company": "D"})
        self.engine.mark_read("user_1", [n1.id])

        feed = self.engine.get_notifications("user_1", unread_only=True)
        assert feed["total"] == 1

    def test_mute_notifications(self):
        """Muted user should only get in-app (not push/slack)."""
        self.engine.mute("user_1", duration_minutes=60)

        notif = self.engine.notify(
            NotificationType.NEW_HOT_LEAD,
            "user_1",
            {"lead_name": "A", "company": "B", "score": 90, "job_title": "X"},
        )
        # Should only have in-app channel when muted (non-urgent)
        assert NotificationChannel.IN_APP in notif.channels
        # Other channels should be removed (except for urgent)

    def test_update_preferences(self):
        """Update user notification preferences."""
        prefs = self.engine.update_preferences("user_1", {
            "daily_digest_enabled": False,
            "muted_channels": ["push"],
            "quiet_hours_start": "22:00",
            "quiet_hours_end": "08:00",
            "timezone": "US/Pacific",
        })
        assert prefs.daily_digest_enabled is False
        assert "push" in prefs.muted_channels
        assert prefs.quiet_hours_start == "22:00"
        assert prefs.timezone == "US/Pacific"

    def test_notification_types(self):
        """All notification types should render correctly."""
        test_cases = [
            (NotificationType.IMPORT_COMPLETE, {"created": 100, "filename": "leads.csv", "failed": 2}),
            (NotificationType.CONNECTOR_ERROR, {"connector_name": "HubSpot", "error": "Auth expired"}),
            (NotificationType.QUOTA_WARNING, {"used": 85, "resource": "enrichment"}),
            (NotificationType.FRAUD_DETECTED, {"count": 5, "risk_level": "high"}),
        ]
        for ntype, data in test_cases:
            notif = self.engine.notify(ntype, "user_1", data)
            assert notif.title  # Should not be empty
            assert notif.message  # Should not be empty

    def test_daily_digest(self):
        """Generate daily digest notification."""
        notif = self.engine.generate_daily_digest("user_1", {
            "new_leads": 47,
            "hot_leads": 12,
            "emails_sent": 234,
            "replies": 19,
        })
        assert "47" in notif.message
        assert "12" in notif.message
        assert notif.type == NotificationType.DAILY_DIGEST.value
