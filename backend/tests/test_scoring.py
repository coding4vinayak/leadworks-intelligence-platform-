"""Tests for the lead scoring engine."""
import pytest
from backend.services.scoring.weighted_scorer import WeightedScorer


class TestWeightedScorer:
    """Test the weighted rule-based scorer."""

    def setup_method(self):
        self.scorer = WeightedScorer(icp={"industries": ["saas", "technology"]})

    def test_score_hot_lead(self):
        """C-level at enterprise company with high engagement should score hot."""
        lead = {
            "job_title": "CEO",
            "company_name": "TechCorp",
            "employee_count": 5000,
            "industry": "saas",
            "email": "ceo@techcorp.com",
            "phone": "+1234567890",
            "linkedin_url": "https://linkedin.com/in/ceo",
            "is_enriched": True,
            "page_visits": 12,
            "emails_sent": 5,
            "emails_opened": 4,
            "emails_clicked": 2,
            "last_responded_at": "2024-01-15",
            "intent_signals": {"visited_pricing": True, "visited_demo": True},
        }
        result = self.scorer.score_lead(lead)
        assert result.total_score >= 60
        assert result.category in ("hot", "warm")
        assert "c_level_title" in result.signals
        assert "enterprise_company" in result.signals

    def test_score_cold_lead(self):
        """Minimal data lead with generic email should score cold."""
        lead = {
            "first_name": "John",
            "email": "john@gmail.com",
        }
        result = self.scorer.score_lead(lead)
        assert result.total_score < 45
        assert result.category == "cold"
        assert "generic_email" in result.penalties

    def test_spam_penalty(self):
        """Spam-flagged lead should get heavy penalty."""
        lead = {
            "email": "test@spam.com",
            "is_spam": True,
        }
        result = self.scorer.score_lead(lead)
        assert result.total_score < 20
        assert "spam_flagged" in result.penalties

    def test_scoring_dimensions(self):
        """All 4 scoring dimensions should be in breakdown."""
        lead = {"email": "john@company.com", "job_title": "Manager"}
        result = self.scorer.score_lead(lead)
        assert "firmographic" in result.breakdown
        assert "behavioral" in result.breakdown
        assert "engagement" in result.breakdown
        assert "enrichment" in result.breakdown

    def test_batch_scoring(self):
        """Batch scoring should process multiple leads."""
        leads = [
            {"email": "a@company.com", "job_title": "CEO"},
            {"email": "b@company.com", "job_title": "Intern"},
            {"email": "c@gmail.com"},
        ]
        results = self.scorer.score_batch(leads)
        assert len(results) == 3
        assert results[0].total_score > results[2].total_score

    def test_confidence_levels(self):
        """Confidence should reflect data completeness."""
        sparse_lead = {"email": "a@b.com"}
        rich_lead = {
            "email": "a@company.com", "first_name": "John",
            "last_name": "Doe", "phone": "+1234567890",
            "job_title": "CTO", "company_name": "Acme",
            "linkedin_url": "https://linkedin.com/in/x",
            "city": "SF", "country": "US",
            "website": "acme.com", "is_enriched": True,
        }
        sparse_result = self.scorer.score_lead(sparse_lead)
        rich_result = self.scorer.score_lead(rich_lead)
        assert sparse_result.confidence == "low"
        assert rich_result.confidence == "high"
