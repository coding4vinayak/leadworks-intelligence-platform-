"""Tests for segmentation engine."""
import pytest
from backend.services.segmentation.segment_engine import SegmentEngine


class TestSegmentEngine:
    """Test the smart segmentation engine."""

    def setup_method(self):
        self.engine = SegmentEngine()

    def test_hot_leads_segment(self):
        """Hot leads segment should match leads with score >= 75."""
        leads = [
            {"id": "1", "score": 92, "status": "qualified"},
            {"id": "2", "score": 50, "status": "new"},
            {"id": "3", "score": 80, "status": "contacted"},
        ]
        members = self.engine.get_segment_members("hot_leads", leads)
        assert len(members) == 2
        assert all(l["score"] >= 75 for l in members)

    def test_evaluate_lead_multiple_segments(self):
        """A lead can belong to multiple segments."""
        lead = {
            "score": 90,
            "source": "linkedin_scrape",
            "is_enriched": False,
            "job_title": "VP Engineering",
            "employee_count": 1000,
        }
        segments = self.engine.evaluate_lead(lead)
        assert "hot_leads" in segments

    def test_create_custom_segment(self):
        """Can create a custom segment with rules."""
        segment = self.engine.create_segment(
            name="SaaS CTOs",
            rules=[
                {"field": "job_title", "operator": "contains", "value": "CTO"},
                {"field": "tags", "operator": "contains", "value": "saas"},
            ],
            logic="and",
        )
        assert segment.id == "saas_ctos"
        assert len(segment.rules) == 2

        # Test matching
        lead = {"job_title": "CTO", "tags": ["saas", "b2b"]}
        segments = self.engine.evaluate_lead(lead)
        assert "saas_ctos" in segments

    def test_segment_or_logic(self):
        """OR logic should match if any rule matches."""
        self.engine.create_segment(
            name="Senior or Enterprise",
            rules=[
                {"field": "job_title", "operator": "contains", "value": "VP"},
                {"field": "employee_count", "operator": "gte", "value": 1000},
            ],
            logic="or",
            segment_id="senior_or_enterprise",
        )

        # Matches on title only
        lead1 = {"job_title": "VP Sales", "employee_count": 50}
        # Matches on company size only
        lead2 = {"job_title": "Manager", "employee_count": 5000}
        # Matches neither
        lead3 = {"job_title": "Intern", "employee_count": 10}

        assert "senior_or_enterprise" in self.engine.evaluate_lead(lead1)
        assert "senior_or_enterprise" in self.engine.evaluate_lead(lead2)
        assert "senior_or_enterprise" not in self.engine.evaluate_lead(lead3)

    def test_suggest_segments(self):
        """AI suggestions should find patterns in lead data."""
        leads = [
            {"source": "linkedin_scrape", "score": 80} for _ in range(15)
        ] + [
            {"source": "google_maps", "score": 40} for _ in range(12)
        ]
        suggestions = self.engine.suggest_segments(leads)
        assert len(suggestions) > 0
        assert any("linkedin" in s["name"].lower() for s in suggestions)

    def test_segment_analytics(self):
        """Should produce meaningful analytics for a segment."""
        leads = [
            {"id": "1", "score": 90, "is_enriched": True, "source": "linkedin", "status": "converted"},
            {"id": "2", "score": 85, "is_enriched": True, "source": "linkedin", "status": "qualified"},
            {"id": "3", "score": 78, "is_enriched": False, "source": "web_form", "status": "new"},
        ]
        analytics = self.engine.get_segment_analytics("hot_leads", leads)
        assert analytics["member_count"] == 3
        assert analytics["avg_score"] > 80
        assert analytics["enriched_percentage"] > 50
