"""Tests for A/B testing engine."""
import pytest
from backend.services.ab_testing.ab_engine import ABTestEngine


class TestABTestEngine:
    """Test the A/B testing engine."""

    def setup_method(self):
        self.engine = ABTestEngine()

    def test_create_test(self):
        """Create a basic A/B test."""
        test = self.engine.create_test(
            name="Subject Line Test",
            test_type="subject",
            variants=[
                {"name": "Short", "subject": "Quick question"},
                {"name": "Long", "subject": "3 ways to improve your pipeline today"},
            ],
            winner_metric="open_rate",
        )
        assert test.status == "draft"
        assert len(test.variants) == 2
        assert test.variants[0].id == "var_A"
        assert test.variants[1].id == "var_B"

    def test_start_test(self):
        """Start a test changes status to running."""
        test = self.engine.create_test(
            name="Test",
            test_type="subject",
            variants=[{"name": "A"}, {"name": "B"}],
        )
        started = self.engine.start_test(test.id)
        assert started.status == "running"
        assert started.started_at is not None

    def test_deterministic_variant_assignment(self):
        """Same lead should always get same variant."""
        test = self.engine.create_test(
            name="Test",
            test_type="subject",
            variants=[{"name": "A"}, {"name": "B"}],
        )
        self.engine.start_test(test.id)

        v1 = self.engine.assign_variant(test.id, "lead_123")
        v2 = self.engine.assign_variant(test.id, "lead_123")
        assert v1.id == v2.id

    def test_different_leads_get_split(self):
        """Different leads should get distributed across variants."""
        test = self.engine.create_test(
            name="Test",
            test_type="subject",
            variants=[{"name": "A"}, {"name": "B"}],
        )
        self.engine.start_test(test.id)

        variants = set()
        for i in range(100):
            v = self.engine.assign_variant(test.id, f"lead_{i}")
            variants.add(v.id)

        # Both variants should be assigned
        assert len(variants) == 2

    def test_record_events(self):
        """Recording events updates variant metrics."""
        test = self.engine.create_test(
            name="Test",
            test_type="subject",
            variants=[{"name": "A"}, {"name": "B"}],
            sample_size=5,
        )
        self.engine.start_test(test.id)

        # Simulate sends and opens
        for _ in range(10):
            self.engine.record_event(test.id, "var_A", "delivered")
            self.engine.record_event(test.id, "var_B", "delivered")

        for _ in range(8):
            self.engine.record_event(test.id, "var_A", "opened")
        for _ in range(3):
            self.engine.record_event(test.id, "var_B", "opened")

        results = self.engine.get_test_results(test.id)
        assert results["variants"][0]["delivered"] == 10
        # Var A has better open rate
        var_a = next(v for v in results["variants"] if v["id"] == "var_A")
        var_b = next(v for v in results["variants"] if v["id"] == "var_B")
        assert var_a["open_rate"] > var_b["open_rate"]

    def test_evaluate_significance(self):
        """With enough data, should detect statistical significance."""
        test = self.engine.create_test(
            name="Test",
            test_type="subject",
            variants=[{"name": "A"}, {"name": "B"}],
            sample_size=50,
            auto_select_winner=False,
        )
        self.engine.start_test(test.id)

        # Give variant A much better performance
        for _ in range(200):
            self.engine.record_event(test.id, "var_A", "delivered")
            self.engine.record_event(test.id, "var_B", "delivered")
        for _ in range(150):
            self.engine.record_event(test.id, "var_A", "opened")
        for _ in range(50):
            self.engine.record_event(test.id, "var_B", "opened")

        evaluation = self.engine.evaluate_test(test.id)
        assert evaluation["sufficient_data"] is True
        # With 75% vs 25% open rate and 200 samples, should be significant
        assert evaluation["statistical_significance"] > 0.9

    def test_suggest_tests(self):
        """Should suggest relevant tests based on campaign data."""
        suggestions = self.engine.suggest_tests({
            "open_rate": 15,
            "click_rate": 2,
            "reply_rate": 1,
        })
        assert len(suggestions) > 0
        assert any(s["test_type"] == "subject" for s in suggestions)
