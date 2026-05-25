"""A/B testing engine for optimizing email subjects, bodies, send times, and CTAs."""
import hashlib
import math
import random
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4
import structlog

logger = structlog.get_logger()


@dataclass
class Variant:
    """A single variant in an A/B test."""
    id: str
    name: str  # e.g. "Subject A", "Body B"
    content: Dict[str, Any] = field(default_factory=dict)
    # Metrics
    sent: int = 0
    delivered: int = 0
    opened: int = 0
    clicked: int = 0
    replied: int = 0
    converted: int = 0
    bounced: int = 0
    unsubscribed: int = 0

    @property
    def open_rate(self) -> float:
        return (self.opened / max(self.delivered, 1)) * 100

    @property
    def click_rate(self) -> float:
        return (self.clicked / max(self.opened, 1)) * 100

    @property
    def reply_rate(self) -> float:
        return (self.replied / max(self.delivered, 1)) * 100

    @property
    def conversion_rate(self) -> float:
        return (self.converted / max(self.delivered, 1)) * 100

    @property
    def bounce_rate(self) -> float:
        return (self.bounced / max(self.sent, 1)) * 100


@dataclass
class ABTest:
    """A/B test definition and results."""
    id: str
    name: str
    campaign_id: Optional[str] = None
    test_type: str = "subject"  # subject, body, send_time, cta, from_name
    status: str = "draft"  # draft, running, completed, winner_selected
    variants: List[Variant] = field(default_factory=list)
    # Config
    traffic_split: List[float] = field(default_factory=lambda: [50.0, 50.0])
    winner_metric: str = "open_rate"  # open_rate, click_rate, reply_rate, conversion_rate
    sample_size: int = 100  # Min sends per variant before declaring winner
    confidence_level: float = 0.95  # Statistical significance threshold
    auto_select_winner: bool = True
    # Results
    winner_variant_id: Optional[str] = None
    statistical_significance: Optional[float] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.utcnow)


class ABTestEngine:
    """
    A/B testing engine for email campaigns.

    Supports testing:
    - Subject lines (most common)
    - Email body/templates
    - Send times (morning vs afternoon vs evening)
    - CTAs (button text, color, placement)
    - From name/address
    - Personalization strategies

    Features:
    - Automatic traffic splitting
    - Statistical significance calculation (chi-squared test)
    - Auto-winner selection when confidence threshold reached
    - Multi-variant support (A/B/C/D)
    - Bandit algorithm option (explore/exploit)
    """

    def __init__(self):
        self.tests: Dict[str, ABTest] = {}

    def create_test(
        self,
        name: str,
        test_type: str,
        variants: List[Dict[str, Any]],
        campaign_id: Optional[str] = None,
        winner_metric: str = "open_rate",
        sample_size: int = 100,
        confidence_level: float = 0.95,
        auto_select_winner: bool = True,
        traffic_split: Optional[List[float]] = None,
    ) -> ABTest:
        """
        Create a new A/B test.

        Args:
            name: Test name
            test_type: What's being tested
            variants: List of variant configs, e.g.
                [{"name": "Short subject", "subject": "Quick question"},
                 {"name": "Long subject", "subject": "3 ways to improve your pipeline"}]
            campaign_id: Associated campaign
            winner_metric: Metric to optimize
            sample_size: Min sends before evaluating
            confidence_level: Required significance (0.90, 0.95, 0.99)
            auto_select_winner: Auto-stop and send winner to remaining list
            traffic_split: Custom split (default: equal)
        """
        test_id = str(uuid4())[:8]

        variant_objects = []
        for i, v in enumerate(variants):
            variant_objects.append(Variant(
                id=f"var_{chr(65 + i)}",  # var_A, var_B, var_C...
                name=v.get("name", f"Variant {chr(65 + i)}"),
                content=v,
            ))

        if not traffic_split:
            n = len(variant_objects)
            traffic_split = [round(100 / n, 1)] * n

        test = ABTest(
            id=test_id,
            name=name,
            campaign_id=campaign_id,
            test_type=test_type,
            variants=variant_objects,
            traffic_split=traffic_split,
            winner_metric=winner_metric,
            sample_size=sample_size,
            confidence_level=confidence_level,
            auto_select_winner=auto_select_winner,
        )

        self.tests[test_id] = test
        logger.info("ab_test_created", test_id=test_id, name=name, variants=len(variant_objects))
        return test

    def start_test(self, test_id: str) -> ABTest:
        """Start running an A/B test."""
        test = self.tests.get(test_id)
        if not test:
            raise ValueError(f"Test {test_id} not found")

        test.status = "running"
        test.started_at = datetime.utcnow()
        logger.info("ab_test_started", test_id=test_id)
        return test

    def assign_variant(self, test_id: str, lead_id: str) -> Variant:
        """
        Assign a lead to a variant using deterministic hashing.
        Ensures same lead always gets same variant (no contamination).
        """
        test = self.tests.get(test_id)
        if not test or test.status != "running":
            raise ValueError(f"Test {test_id} not running")

        # Deterministic assignment based on lead_id hash
        hash_input = f"{test_id}:{lead_id}"
        hash_val = int(hashlib.md5(hash_input.encode()).hexdigest(), 16)
        bucket = hash_val % 10000  # 0-9999 for precision

        # Map bucket to variant based on traffic split
        cumulative = 0
        for i, (variant, split) in enumerate(zip(test.variants, test.traffic_split)):
            cumulative += split * 100  # Convert percentage to basis points
            if bucket < cumulative:
                return variant

        # Fallback to last variant
        return test.variants[-1]

    def record_event(
        self,
        test_id: str,
        variant_id: str,
        event_type: str,
    ) -> Dict[str, Any]:
        """
        Record an event (open, click, reply, convert) for a variant.

        Args:
            test_id: The test
            variant_id: Which variant
            event_type: sent, delivered, opened, clicked, replied, converted, bounced, unsubscribed
        """
        test = self.tests.get(test_id)
        if not test:
            return {"error": "Test not found"}

        variant = next((v for v in test.variants if v.id == variant_id), None)
        if not variant:
            return {"error": "Variant not found"}

        # Increment counter
        if event_type == "sent":
            variant.sent += 1
        elif event_type == "delivered":
            variant.delivered += 1
        elif event_type == "opened":
            variant.opened += 1
        elif event_type == "clicked":
            variant.clicked += 1
        elif event_type == "replied":
            variant.replied += 1
        elif event_type == "converted":
            variant.converted += 1
        elif event_type == "bounced":
            variant.bounced += 1
        elif event_type == "unsubscribed":
            variant.unsubscribed += 1

        # Check if we should evaluate results
        result = {"recorded": True, "event_type": event_type, "variant_id": variant_id}

        if test.auto_select_winner:
            min_sends = min(v.delivered for v in test.variants)
            if min_sends >= test.sample_size:
                evaluation = self.evaluate_test(test_id)
                if evaluation.get("has_winner"):
                    result["winner_found"] = True
                    result["winner"] = evaluation["winner"]

        return result

    def evaluate_test(self, test_id: str) -> Dict[str, Any]:
        """
        Evaluate test results with statistical significance.
        Uses chi-squared test for proportions.
        """
        test = self.tests.get(test_id)
        if not test:
            return {"error": "Test not found"}

        if len(test.variants) < 2:
            return {"error": "Need at least 2 variants"}

        # Get metric values for each variant
        metric = test.winner_metric
        variant_metrics = []
        for v in test.variants:
            if metric == "open_rate":
                rate = v.open_rate
            elif metric == "click_rate":
                rate = v.click_rate
            elif metric == "reply_rate":
                rate = v.reply_rate
            elif metric == "conversion_rate":
                rate = v.conversion_rate
            else:
                rate = v.open_rate
            variant_metrics.append({"variant": v, "rate": rate})

        # Sort by rate (best first)
        variant_metrics.sort(key=lambda x: x["rate"], reverse=True)
        best = variant_metrics[0]
        second = variant_metrics[1]

        # Calculate statistical significance (simplified z-test for proportions)
        significance = self._calculate_significance(
            best["variant"], second["variant"], metric
        )

        has_winner = significance >= test.confidence_level
        sufficient_data = all(v.delivered >= test.sample_size for v in test.variants)

        result = {
            "test_id": test_id,
            "status": test.status,
            "has_winner": has_winner and sufficient_data,
            "statistical_significance": round(significance, 4),
            "confidence_level_required": test.confidence_level,
            "sufficient_data": sufficient_data,
            "winner_metric": metric,
            "variants": [],
        }

        for vm in variant_metrics:
            v = vm["variant"]
            result["variants"].append({
                "id": v.id,
                "name": v.name,
                "delivered": v.delivered,
                "rate": round(vm["rate"], 2),
                "open_rate": round(v.open_rate, 2),
                "click_rate": round(v.click_rate, 2),
                "reply_rate": round(v.reply_rate, 2),
                "conversion_rate": round(v.conversion_rate, 2),
                "is_winner": has_winner and v.id == best["variant"].id,
            })

        if has_winner and sufficient_data:
            result["winner"] = {
                "variant_id": best["variant"].id,
                "variant_name": best["variant"].name,
                "rate": round(best["rate"], 2),
                "improvement": round(best["rate"] - second["rate"], 2),
                "improvement_percentage": round(
                    ((best["rate"] - second["rate"]) / max(second["rate"], 0.01)) * 100, 1
                ),
            }

            # Auto-complete test
            if test.auto_select_winner and test.status == "running":
                test.status = "winner_selected"
                test.winner_variant_id = best["variant"].id
                test.statistical_significance = significance
                test.completed_at = datetime.utcnow()
                logger.info(
                    "ab_test_winner_selected",
                    test_id=test_id,
                    winner=best["variant"].name,
                    significance=significance,
                )

        return result

    def get_test_results(self, test_id: str) -> Dict[str, Any]:
        """Get current test results without triggering evaluation."""
        test = self.tests.get(test_id)
        if not test:
            return {"error": "Test not found"}

        return {
            "id": test.id,
            "name": test.name,
            "test_type": test.test_type,
            "status": test.status,
            "winner_metric": test.winner_metric,
            "started_at": test.started_at.isoformat() if test.started_at else None,
            "completed_at": test.completed_at.isoformat() if test.completed_at else None,
            "winner_variant_id": test.winner_variant_id,
            "variants": [
                {
                    "id": v.id,
                    "name": v.name,
                    "content": v.content,
                    "sent": v.sent,
                    "delivered": v.delivered,
                    "opened": v.opened,
                    "clicked": v.clicked,
                    "replied": v.replied,
                    "converted": v.converted,
                    "open_rate": round(v.open_rate, 2),
                    "click_rate": round(v.click_rate, 2),
                    "reply_rate": round(v.reply_rate, 2),
                    "conversion_rate": round(v.conversion_rate, 2),
                }
                for v in test.variants
            ],
        }

    def suggest_tests(self, campaign_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Suggest A/B tests based on campaign performance data."""
        suggestions = []

        open_rate = campaign_data.get("open_rate", 0)
        click_rate = campaign_data.get("click_rate", 0)
        reply_rate = campaign_data.get("reply_rate", 0)

        if open_rate < 25:
            suggestions.append({
                "test_type": "subject",
                "reason": f"Low open rate ({open_rate}%) - test different subject lines",
                "variants_suggestion": [
                    "Short & direct (5-7 words)",
                    "Question format",
                    "Personalized with company name",
                    "Urgency/FOMO angle",
                ],
            })

        if open_rate > 20 and click_rate < 3:
            suggestions.append({
                "test_type": "body",
                "reason": f"Good opens ({open_rate}%) but low clicks ({click_rate}%) - test body copy",
                "variants_suggestion": [
                    "Shorter body with single CTA",
                    "Story-driven with social proof",
                    "Value-first with bullet points",
                ],
            })

        if click_rate > 5 and reply_rate < 2:
            suggestions.append({
                "test_type": "cta",
                "reason": f"Good clicks ({click_rate}%) but low replies ({reply_rate}%) - test CTAs",
                "variants_suggestion": [
                    "Direct question CTA",
                    "Low-commitment CTA (quick chat)",
                    "Value-offer CTA (free audit/demo)",
                ],
            })

        suggestions.append({
            "test_type": "send_time",
            "reason": "Always worth testing send times",
            "variants_suggestion": [
                "Tuesday 9am",
                "Wednesday 2pm",
                "Thursday 7am",
                "Monday 11am",
            ],
        })

        return suggestions

    def _calculate_significance(
        self, variant_a: Variant, variant_b: Variant, metric: str
    ) -> float:
        """
        Calculate statistical significance using z-test for proportions.
        Returns confidence level (0-1).
        """
        # Get success counts and totals
        if metric == "open_rate":
            s1, n1 = variant_a.opened, max(variant_a.delivered, 1)
            s2, n2 = variant_b.opened, max(variant_b.delivered, 1)
        elif metric == "click_rate":
            s1, n1 = variant_a.clicked, max(variant_a.opened, 1)
            s2, n2 = variant_b.clicked, max(variant_b.opened, 1)
        elif metric == "reply_rate":
            s1, n1 = variant_a.replied, max(variant_a.delivered, 1)
            s2, n2 = variant_b.replied, max(variant_b.delivered, 1)
        elif metric == "conversion_rate":
            s1, n1 = variant_a.converted, max(variant_a.delivered, 1)
            s2, n2 = variant_b.converted, max(variant_b.delivered, 1)
        else:
            return 0.0

        if n1 < 10 or n2 < 10:
            return 0.0  # Not enough data

        p1 = s1 / n1
        p2 = s2 / n2
        p_pool = (s1 + s2) / (n1 + n2)

        if p_pool == 0 or p_pool == 1:
            return 0.0

        # Standard error
        se = math.sqrt(p_pool * (1 - p_pool) * (1/n1 + 1/n2))
        if se == 0:
            return 0.0

        # Z-score
        z = abs(p1 - p2) / se

        # Convert z-score to confidence (approximate using normal CDF)
        confidence = self._z_to_confidence(z)
        return confidence

    def _z_to_confidence(self, z: float) -> float:
        """Approximate normal CDF for z-score -> confidence."""
        # Using Abramowitz and Stegun approximation
        if z < 0:
            return 0.5
        t = 1.0 / (1.0 + 0.2316419 * z)
        d = 0.3989422804014327
        p = d * math.exp(-z * z / 2.0) * (
            t * (0.3193815 + t * (-0.3565638 + t * (1.781478 + t * (-1.821256 + t * 1.330274))))
        )
        return 1.0 - p

    def list_tests(self, campaign_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """List all A/B tests, optionally filtered by campaign."""
        tests = self.tests.values()
        if campaign_id:
            tests = [t for t in tests if t.campaign_id == campaign_id]

        return [
            {
                "id": t.id,
                "name": t.name,
                "test_type": t.test_type,
                "status": t.status,
                "variants_count": len(t.variants),
                "winner_metric": t.winner_metric,
                "winner_variant_id": t.winner_variant_id,
                "started_at": t.started_at.isoformat() if t.started_at else None,
            }
            for t in tests
        ]
