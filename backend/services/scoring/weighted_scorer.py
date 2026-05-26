"""Weighted rule-based lead scoring."""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import structlog

logger = structlog.get_logger()


@dataclass
class ScoreResult:
    """Result from scoring a lead."""
    total_score: float = 0.0
    category: str = "cold"  # hot, warm, cold
    breakdown: Dict[str, float] = field(default_factory=dict)
    signals: List[str] = field(default_factory=list)
    penalties: List[str] = field(default_factory=list)
    confidence: str = "medium"


# Default scoring weights and rules
DEFAULT_SCORING_CONFIG = {
    "weights": {
        "firmographic": 0.30,
        "behavioral": 0.30,
        "engagement": 0.25,
        "enrichment": 0.15,
    },
    "thresholds": {
        "hot": 75,
        "warm": 45,
        "cold": 0,
    },
    "firmographic_rules": {
        # Job title seniority scoring
        "seniority": {
            "c_level": 25,   # CEO, CTO, CFO, CMO, COO
            "vp": 22,        # VP of X
            "director": 18,
            "head": 16,      # Head of X
            "manager": 12,
            "senior": 10,
            "lead": 8,
            "other": 3,
        },
        # Company size scoring
        "company_size": {
            "enterprise": 20,    # 1000+
            "mid_market": 18,    # 201-1000
            "growth": 15,        # 51-200
            "small": 10,         # 11-50
            "startup": 8,        # 1-10
        },
        # Industry match (configurable per team)
        "industry_match": 15,
        "industry_partial_match": 8,
        # Location match
        "location_match": 5,
    },
    "behavioral_rules": {
        "visited_pricing_page": 20,
        "visited_demo_page": 18,
        "visited_case_study": 12,
        "visited_blog": 5,
        "visited_docs": 8,
        "form_submission": 25,
        "content_download": 15,
        "webinar_attended": 18,
        "trial_signup": 30,
        "page_visits_5plus": 10,
        "page_visits_10plus": 15,
        "return_visitor": 12,
        "time_on_site_5min": 8,
        "time_on_site_10min": 12,
    },
    "engagement_rules": {
        "email_opened": 5,
        "email_clicked": 12,
        "email_replied": 25,
        "meeting_booked": 30,
        "proposal_viewed": 20,
        "multiple_opens": 8,     # Opened 3+ emails
        "fast_response": 15,     # Replied within 24h
        "linkedin_connected": 10,
        "referred_others": 20,
    },
    "enrichment_bonus": {
        "has_linkedin": 5,
        "has_phone": 5,
        "verified_email": 5,
        "company_enriched": 8,
        "tech_stack_match": 12,
        "recent_funding": 15,
        "hiring_signal": 10,
    },
    "penalties": {
        "generic_email": -10,      # gmail, yahoo, etc.
        "no_company": -8,
        "bounced_email": -20,
        "unsubscribed": -30,
        "competitor": -25,
        "spam_flagged": -50,
        "no_engagement_30_days": -15,
        "invalid_phone": -5,
    },
}


class WeightedScorer:
    """
    Rule-based weighted lead scoring system.

    Scores leads based on configurable rules across 4 dimensions:
    1. Firmographic (who they are)
    2. Behavioral (what they do on site)
    3. Engagement (how they respond)
    4. Enrichment quality (data completeness)
    """

    def __init__(self, config: Optional[Dict] = None, icp: Optional[Dict] = None):
        self.config = config or DEFAULT_SCORING_CONFIG
        self.icp = icp or {}  # Ideal Customer Profile for matching

    def score_lead(self, lead_data: Dict[str, Any]) -> ScoreResult:
        """Score a single lead based on all dimensions."""
        result = ScoreResult()

        # Calculate each dimension
        firmographic = self._score_firmographic(lead_data)
        behavioral = self._score_behavioral(lead_data)
        engagement = self._score_engagement(lead_data)
        enrichment = self._score_enrichment(lead_data)
        penalties = self._calculate_penalties(lead_data)

        # Weight and combine
        weights = self.config["weights"]
        raw_score = (
            firmographic["score"] * weights["firmographic"]
            + behavioral["score"] * weights["behavioral"]
            + engagement["score"] * weights["engagement"]
            + enrichment["score"] * weights["enrichment"]
        )

        # Apply penalties
        penalty_total = sum(p["value"] for p in penalties)

        # Normalize to 0-100
        total = max(0, min(100, raw_score + penalty_total))

        # Build result
        result.total_score = round(total, 1)
        result.breakdown = {
            "firmographic": round(firmographic["score"] * weights["firmographic"], 1),
            "behavioral": round(behavioral["score"] * weights["behavioral"], 1),
            "engagement": round(engagement["score"] * weights["engagement"], 1),
            "enrichment": round(enrichment["score"] * weights["enrichment"], 1),
            "penalties": round(penalty_total, 1),
        }
        result.signals = firmographic["signals"] + behavioral["signals"] + engagement["signals"]
        result.penalties = [p["reason"] for p in penalties]

        # Determine category
        thresholds = self.config["thresholds"]
        if total >= thresholds["hot"]:
            result.category = "hot"
        elif total >= thresholds["warm"]:
            result.category = "warm"
        else:
            result.category = "cold"

        # Confidence based on data completeness
        data_points = sum(1 for v in lead_data.values() if v)
        if data_points >= 10:
            result.confidence = "high"
        elif data_points >= 5:
            result.confidence = "medium"
        else:
            result.confidence = "low"

        return result

    def _score_firmographic(self, lead: Dict) -> Dict:
        """Score based on who the lead is."""
        score = 0.0
        signals = []
        rules = self.config["firmographic_rules"]

        # Job title / seniority
        title = (lead.get("job_title") or "").lower()
        seniority_scores = rules["seniority"]

        if any(t in title for t in ["ceo", "cto", "cfo", "cmo", "coo", "founder", "co-founder", "chief"]):
            score += seniority_scores["c_level"]
            signals.append("c_level_title")
        elif any(t in title for t in ["vp", "vice president"]):
            score += seniority_scores["vp"]
            signals.append("vp_title")
        elif "director" in title:
            score += seniority_scores["director"]
            signals.append("director_title")
        elif any(t in title for t in ["head of", "head,"]):
            score += seniority_scores["head"]
            signals.append("head_title")
        elif "manager" in title:
            score += seniority_scores["manager"]
            signals.append("manager_title")
        elif "senior" in title or "sr." in title:
            score += seniority_scores["senior"]
            signals.append("senior_title")
        elif "lead" in title:
            score += seniority_scores["lead"]
            signals.append("lead_title")
        elif title:
            score += seniority_scores["other"]

        # Company size
        employee_count = lead.get("employee_count") or 0
        if employee_count >= 1000:
            score += rules["company_size"]["enterprise"]
            signals.append("enterprise_company")
        elif employee_count >= 201:
            score += rules["company_size"]["mid_market"]
            signals.append("mid_market_company")
        elif employee_count >= 51:
            score += rules["company_size"]["growth"]
            signals.append("growth_company")
        elif employee_count >= 11:
            score += rules["company_size"]["small"]
            signals.append("small_company")
        elif employee_count >= 1:
            score += rules["company_size"]["startup"]
            signals.append("startup_company")

        # ICP industry match
        if self.icp.get("industries"):
            lead_industry = (lead.get("industry") or "").lower()
            if lead_industry in [i.lower() for i in self.icp["industries"]]:
                score += rules["industry_match"]
                signals.append("industry_match")

        # Normalize firmographic score to 0-100
        max_possible = 25 + 20 + 15 + 5  # max seniority + size + industry + location
        score = min(100, (score / max_possible) * 100) if max_possible > 0 else 0

        return {"score": score, "signals": signals}

    def _score_behavioral(self, lead: Dict) -> Dict:
        """Score based on website/product behavior."""
        score = 0.0
        signals = []
        rules = self.config["behavioral_rules"]

        # Page visits
        page_visits = lead.get("page_visits") or 0
        if page_visits >= 10:
            score += rules["page_visits_10plus"]
            signals.append("page_visits_10plus")
        elif page_visits >= 5:
            score += rules["page_visits_5plus"]
            signals.append("page_visits_5plus")

        # Specific page visits (from activity/intent data)
        intent = lead.get("intent_signals") or {}
        if isinstance(intent, dict):
            if intent.get("visited_pricing"):
                score += rules["visited_pricing_page"]
                signals.append("visited_pricing_page")
            if intent.get("visited_demo"):
                score += rules["visited_demo_page"]
                signals.append("visited_demo_page")
            if intent.get("form_submission"):
                score += rules["form_submission"]
                signals.append("form_submission")
            if intent.get("trial_signup"):
                score += rules["trial_signup"]
                signals.append("trial_signup")
            if intent.get("content_download"):
                score += rules["content_download"]
                signals.append("content_download")

        # Normalize to 0-100
        max_possible = 30 + 20 + 18 + 25 + 15 + 15  # reasonable max
        score = min(100, (score / max_possible) * 100) if max_possible > 0 else 0

        return {"score": score, "signals": signals}

    def _score_engagement(self, lead: Dict) -> Dict:
        """Score based on engagement with outreach."""
        score = 0.0
        signals = []
        rules = self.config["engagement_rules"]

        emails_opened = lead.get("emails_opened") or 0
        emails_clicked = lead.get("emails_clicked") or 0

        if emails_opened >= 3:
            score += rules["multiple_opens"]
            signals.append("multiple_email_opens")
        elif emails_opened >= 1:
            score += rules["email_opened"]
            signals.append("email_opened")

        if emails_clicked >= 1:
            score += rules["email_clicked"]
            signals.append("email_clicked")

        if lead.get("last_responded_at"):
            score += rules["email_replied"]
            signals.append("email_replied")

        if lead.get("linkedin_url"):
            score += rules["linkedin_connected"]
            signals.append("has_linkedin")

        # Normalize to 0-100
        max_possible = 25 + 12 + 30 + 8 + 10
        score = min(100, (score / max_possible) * 100) if max_possible > 0 else 0

        return {"score": score, "signals": signals}

    def _score_enrichment(self, lead: Dict) -> Dict:
        """Score based on data completeness and quality signals."""
        score = 0.0
        signals = []
        rules = self.config["enrichment_bonus"]

        if lead.get("linkedin_url"):
            score += rules["has_linkedin"]
            signals.append("has_linkedin")
        if lead.get("phone"):
            score += rules["has_phone"]
            signals.append("has_phone")
        if lead.get("is_enriched"):
            score += rules["company_enriched"]
            signals.append("company_enriched")

        # Tech stack match with ICP
        tech_stack = lead.get("tech_stack") or []
        icp_tech = self.icp.get("tech_stack") or []
        if tech_stack and icp_tech:
            overlap = set(t.lower() for t in tech_stack) & set(t.lower() for t in icp_tech)
            if overlap:
                score += rules["tech_stack_match"]
                signals.append(f"tech_match:{','.join(list(overlap)[:3])}")

        # Normalize to 0-100
        max_possible = 5 + 5 + 5 + 8 + 12 + 15 + 10
        score = min(100, (score / max_possible) * 100) if max_possible > 0 else 0

        return {"score": score, "signals": signals}

    def _calculate_penalties(self, lead: Dict) -> List[Dict]:
        """Calculate score penalties."""
        penalties = []
        rules = self.config["penalties"]

        email = lead.get("email", "")
        if email:
            domain = email.split("@")[-1].lower() if "@" in email else ""
            generic_domains = {"gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "icloud.com", "aol.com"}
            if domain in generic_domains:
                penalties.append({"reason": "generic_email", "value": rules["generic_email"]})

        if not lead.get("company_name"):
            penalties.append({"reason": "no_company", "value": rules["no_company"]})

        if lead.get("is_spam"):
            penalties.append({"reason": "spam_flagged", "value": rules["spam_flagged"]})

        return penalties

    def score_batch(self, leads: List[Dict]) -> List[ScoreResult]:
        """Score multiple leads."""
        return [self.score_lead(lead) for lead in leads]
