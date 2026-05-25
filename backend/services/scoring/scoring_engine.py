"""Scoring engine - combines weighted + ML scoring with hybrid approach."""
from typing import Any, Dict, List, Optional
import structlog

from backend.services.scoring.weighted_scorer import WeightedScorer, ScoreResult
from backend.services.scoring.ml_scorer import MLScorer

logger = structlog.get_logger()


class ScoringEngine:
    """
    Hybrid scoring engine that combines:
    1. Weighted rule-based scoring (always available, transparent)
    2. ML predictive scoring (when trained model available)

    Strategy:
    - New accounts start with weighted scoring only
    - Once enough conversion data exists (100+ leads), train ML model
    - Use weighted score as baseline, ML as boost/modifier
    - A/B test different models against conversion rates
    """

    def __init__(
        self,
        scoring_config: Optional[Dict] = None,
        icp: Optional[Dict] = None,
        ml_model_path: Optional[str] = None,
        hybrid_weight: float = 0.6,
    ):
        """
        Args:
            scoring_config: Custom weights/rules config
            icp: Ideal Customer Profile for matching
            ml_model_path: Path to trained ML model
            hybrid_weight: Weight for ML score in hybrid (0-1).
                          0 = all weighted, 1 = all ML
        """
        self.weighted_scorer = WeightedScorer(config=scoring_config, icp=icp)
        self.ml_scorer = MLScorer(model_path=ml_model_path)
        self.hybrid_weight = hybrid_weight
        self.icp = icp or {}

    def score_lead(
        self,
        lead_data: Dict[str, Any],
        mode: str = "hybrid",
    ) -> Dict[str, Any]:
        """
        Score a lead using the specified strategy.

        Args:
            lead_data: Lead data dict
            mode: "weighted", "ml", or "hybrid"

        Returns:
            Comprehensive scoring result with breakdown
        """
        result = {
            "lead_id": lead_data.get("id"),
            "timestamp": None,
            "mode": mode,
        }

        # Always calculate weighted score (transparent, explainable)
        weighted_result = self.weighted_scorer.score_lead(lead_data)
        result["weighted_score"] = {
            "total": weighted_result.total_score,
            "category": weighted_result.category,
            "breakdown": weighted_result.breakdown,
            "signals": weighted_result.signals,
            "penalties": weighted_result.penalties,
            "confidence": weighted_result.confidence,
        }

        # ML score (if model available)
        ml_result = None
        if mode in ("ml", "hybrid") and self.ml_scorer.model is not None:
            ml_result = self.ml_scorer.predict_score(lead_data)
            result["ml_score"] = ml_result

        # Final score
        if mode == "weighted" or self.ml_scorer.model is None:
            result["final_score"] = weighted_result.total_score
            result["final_category"] = weighted_result.category
        elif mode == "ml" and ml_result:
            result["final_score"] = ml_result["score"]
            result["final_category"] = ml_result["category"]
        elif mode == "hybrid" and ml_result:
            # Blend weighted and ML scores
            w = self.hybrid_weight
            hybrid_score = (ml_result["score"] * w) + (weighted_result.total_score * (1 - w))
            result["final_score"] = round(hybrid_score, 1)
            result["final_category"] = self._categorize(hybrid_score)
        else:
            result["final_score"] = weighted_result.total_score
            result["final_category"] = weighted_result.category

        # Add recommendations
        result["recommendations"] = self._generate_recommendations(
            result["final_score"],
            result["final_category"],
            weighted_result.signals,
            lead_data,
        )

        return result

    def score_batch(
        self,
        leads: List[Dict[str, Any]],
        mode: str = "hybrid",
    ) -> List[Dict[str, Any]]:
        """Score multiple leads efficiently."""
        results = []

        # Batch ML predictions if available
        ml_scores = {}
        if mode in ("ml", "hybrid") and self.ml_scorer.model is not None:
            ml_batch = self.ml_scorer.predict_batch(leads)
            for i, ml_result in enumerate(ml_batch):
                ml_scores[i] = ml_result

        for i, lead in enumerate(leads):
            weighted_result = self.weighted_scorer.score_lead(lead)

            if mode == "weighted" or self.ml_scorer.model is None:
                final_score = weighted_result.total_score
            elif mode == "ml" and i in ml_scores:
                final_score = ml_scores[i]["score"]
            elif mode == "hybrid" and i in ml_scores:
                w = self.hybrid_weight
                final_score = round(
                    (ml_scores[i]["score"] * w) + (weighted_result.total_score * (1 - w)), 1
                )
            else:
                final_score = weighted_result.total_score

            results.append({
                "lead_id": lead.get("id"),
                "final_score": final_score,
                "final_category": self._categorize(final_score),
                "weighted_score": weighted_result.total_score,
                "ml_score": ml_scores.get(i, {}).get("score"),
                "signals": weighted_result.signals[:5],
            })

        return results

    def train_ml_model(
        self,
        training_data: List[Dict],
        labels: List[int],
        model_type: str = "xgboost",
    ) -> Dict[str, Any]:
        """Train the ML scoring model."""
        return self.ml_scorer.train(training_data, labels, model_type=model_type)

    def update_icp(self, icp: Dict[str, Any]):
        """Update the Ideal Customer Profile."""
        self.icp = icp
        self.weighted_scorer.icp = icp

    def _categorize(self, score: float) -> str:
        """Categorize score into hot/warm/cold."""
        if score >= 75:
            return "hot"
        elif score >= 45:
            return "warm"
        return "cold"

    def _generate_recommendations(
        self,
        score: float,
        category: str,
        signals: List[str],
        lead_data: Dict,
    ) -> List[str]:
        """Generate actionable recommendations based on score."""
        recs = []

        if category == "hot":
            recs.append("Prioritize immediate outreach - this lead shows high intent")
            if "visited_pricing_page" in signals:
                recs.append("Lead viewed pricing - discuss budget and timeline")
            if "email_replied" in signals:
                recs.append("Lead is engaged - book a meeting ASAP")
            recs.append("Consider assigning to senior sales rep")

        elif category == "warm":
            if not lead_data.get("is_enriched"):
                recs.append("Enrich this lead for more context before outreach")
            if not signals or len(signals) < 3:
                recs.append("Need more engagement data - add to nurture campaign")
            recs.append("Schedule follow-up in 2-3 days")
            if "c_level_title" in signals or "vp_title" in signals:
                recs.append("High seniority - personalize messaging")

        else:  # cold
            if not lead_data.get("email"):
                recs.append("Find email address via enrichment")
            recs.append("Add to awareness campaign or long-term nurture")
            if lead_data.get("company_name"):
                recs.append("Research company for better targeting")
            recs.append("Re-score after 2 weeks of nurturing")

        return recs[:4]
