"""Tests for lead routing engine."""
import pytest
from backend.services.routing.router import LeadRouter, SalesRep, RoutingRule, RoutingStrategy


class TestLeadRouter:
    """Test lead routing/assignment."""

    def setup_method(self):
        self.router = LeadRouter()
        # Add reps
        self.router.add_rep(SalesRep(
            id="rep_1", name="Alice", email="alice@company.com",
            capacity=50, territories=["US", "Canada"],
            industries=["saas"], skills=["enterprise"],
            min_score_threshold=50, max_score_threshold=100,
        ))
        self.router.add_rep(SalesRep(
            id="rep_2", name="Bob", email="bob@company.com",
            capacity=50, territories=["UK", "Germany"],
            industries=["fintech"], skills=["mid_market"],
        ))
        self.router.add_rep(SalesRep(
            id="rep_3", name="Charlie", email="charlie@company.com",
            capacity=30, current_load=25,
            territories=["US"], skills=["startup"],
            min_score_threshold=0, max_score_threshold=50,
        ))

    def test_round_robin(self):
        """Round robin should cycle through reps."""
        leads = [{"id": f"lead_{i}"} for i in range(6)]
        results = self.router.route_batch(leads, RoutingStrategy.ROUND_ROBIN)
        assert len(results) == 6
        # All should be assigned
        assert all(r["assigned_to"] is not None for r in results)

    def test_territory_routing(self):
        """Territory routing should match by geography."""
        lead_us = {"id": "1", "country": "US", "city": "New York"}
        lead_uk = {"id": "2", "country": "UK", "city": "London"}

        result_us = self.router.route_lead(lead_us, RoutingStrategy.TERRITORY)
        result_uk = self.router.route_lead(lead_uk, RoutingStrategy.TERRITORY)

        assert result_us["assigned_to"] in ("rep_1", "rep_3")  # Both have US territory
        assert result_uk["assigned_to"] == "rep_2"

    def test_load_balanced(self):
        """Load balanced should prefer rep with lowest utilization."""
        lead = {"id": "test"}
        result = self.router.route_lead(lead, RoutingStrategy.LOAD_BALANCED)
        # rep_1 and rep_2 have 0 load, rep_3 has 25/30
        assert result["assigned_to"] in ("rep_1", "rep_2")

    def test_score_based_routing(self):
        """High-score leads should go to senior reps."""
        hot_lead = {"id": "1", "score": 85}
        cold_lead = {"id": "2", "score": 20}

        result_hot = self.router.route_lead(hot_lead, RoutingStrategy.SCORE_BASED)
        result_cold = self.router.route_lead(cold_lead, RoutingStrategy.SCORE_BASED)

        # Hot lead should go to rep_1 (threshold 50-100)
        assert result_hot["assigned_to"] == "rep_1"
        # Cold lead should go to rep_3 (threshold 0-50)
        assert result_cold["assigned_to"] == "rep_3"

    def test_capacity_respected(self):
        """Reps at capacity should not receive leads."""
        # Fill up all reps
        self.router.reps["rep_1"].current_load = 50
        self.router.reps["rep_2"].current_load = 50
        self.router.reps["rep_3"].current_load = 30

        lead = {"id": "overflow"}
        result = self.router.route_lead(lead)
        assert result["assigned_to"] is None
        assert result["reason"] == "no_reps_available"

    def test_rule_based_routing(self):
        """Rules should override default strategy."""
        self.router.add_rule(RoutingRule(
            id="enterprise_rule",
            name="Enterprise to Alice",
            priority=1,
            conditions=[{"field": "employee_count", "operator": "gte", "value": 1000}],
            target_rep_ids=["rep_1"],
            strategy=RoutingStrategy.ROUND_ROBIN,
        ))

        enterprise_lead = {"id": "1", "employee_count": 5000}
        result = self.router.route_lead(enterprise_lead)
        assert result["assigned_to"] == "rep_1"
        assert "rule:Enterprise to Alice" in result["reason"]

    def test_rep_stats(self):
        """Should track assignment statistics."""
        for i in range(5):
            self.router.route_lead({"id": f"lead_{i}"}, RoutingStrategy.ROUND_ROBIN)

        stats = self.router.get_rep_stats()
        assert len(stats) == 3
        total_assigned = sum(s["total_assigned"] for s in stats)
        assert total_assigned == 5
