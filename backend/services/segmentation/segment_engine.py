"""Smart segmentation engine - dynamic segments, AI suggestions, auto-grouping."""
import enum
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional, Set, Tuple
import structlog

logger = structlog.get_logger()


class SegmentOperator(str, enum.Enum):
    EQUALS = "eq"
    NOT_EQUALS = "neq"
    GREATER_THAN = "gt"
    GREATER_EQUAL = "gte"
    LESS_THAN = "lt"
    LESS_EQUAL = "lte"
    CONTAINS = "contains"
    NOT_CONTAINS = "not_contains"
    STARTS_WITH = "starts_with"
    ENDS_WITH = "ends_with"
    IN = "in"
    NOT_IN = "not_in"
    EXISTS = "exists"
    NOT_EXISTS = "not_exists"
    BETWEEN = "between"
    DAYS_AGO_LESS = "days_ago_less"
    DAYS_AGO_MORE = "days_ago_more"


@dataclass
class SegmentRule:
    """A single rule within a segment definition."""
    field: str
    operator: SegmentOperator
    value: Any
    negate: bool = False


@dataclass
class Segment:
    """A dynamic segment definition."""
    id: str
    name: str
    description: str = ""
    rules: List[SegmentRule] = field(default_factory=list)
    logic: str = "and"  # "and" or "or"
    is_dynamic: bool = True  # Dynamic = auto-updated, Static = manual
    is_ai_generated: bool = False
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    member_count: int = 0
    tags: List[str] = field(default_factory=list)


# Pre-built smart segments
DEFAULT_SEGMENTS = [
    Segment(
        id="hot_leads",
        name="Hot Leads",
        description="Leads with score >= 75, high buying intent",
        rules=[SegmentRule("score", SegmentOperator.GREATER_EQUAL, 75)],
    ),
    Segment(
        id="enterprise_decision_makers",
        name="Enterprise Decision Makers",
        description="C-level/VP at companies with 500+ employees",
        rules=[
            SegmentRule("job_title", SegmentOperator.CONTAINS, "VP"),
            SegmentRule("employee_count", SegmentOperator.GREATER_EQUAL, 500),
        ],
        logic="and",
    ),
    Segment(
        id="engaged_no_reply",
        name="Engaged but No Reply",
        description="Opened 3+ emails but never replied",
        rules=[
            SegmentRule("emails_opened", SegmentOperator.GREATER_EQUAL, 3),
            SegmentRule("last_responded_at", SegmentOperator.NOT_EXISTS, None),
        ],
    ),
    Segment(
        id="stale_leads",
        name="Stale Leads (30+ days inactive)",
        description="No activity in 30+ days, may need re-engagement",
        rules=[
            SegmentRule("last_activity_at", SegmentOperator.DAYS_AGO_MORE, 30),
        ],
    ),
    Segment(
        id="linkedin_sourced_unenriched",
        name="LinkedIn Leads - Not Enriched",
        description="Came from LinkedIn but missing key data",
        rules=[
            SegmentRule("source", SegmentOperator.EQUALS, "linkedin_scrape"),
            SegmentRule("is_enriched", SegmentOperator.EQUALS, False),
        ],
    ),
    Segment(
        id="high_intent_visitors",
        name="High Intent Website Visitors",
        description="Visited pricing/demo pages or submitted a form",
        rules=[
            SegmentRule("intent_signals", SegmentOperator.CONTAINS, "visited_pricing"),
        ],
        logic="or",
    ),
    Segment(
        id="tech_match_icp",
        name="ICP Tech Stack Match",
        description="Company uses tech matching your ICP",
        rules=[
            SegmentRule("tech_stack_match_score", SegmentOperator.GREATER_THAN, 0.5),
        ],
        is_ai_generated=True,
    ),
    Segment(
        id="recently_funded",
        name="Recently Funded Companies",
        description="Companies that raised funding recently",
        rules=[
            SegmentRule("funding_stage", SegmentOperator.EXISTS, None),
            SegmentRule("company_size_category", SegmentOperator.IN, ["startup", "growth"]),
        ],
        is_ai_generated=True,
    ),
]


class SegmentEngine:
    """
    Smart segmentation engine that:
    - Evaluates leads against segment rules in real-time
    - Auto-generates segments using AI analysis of lead data
    - Supports compound rules (AND/OR logic)
    - Recalculates segment membership on lead changes
    - Suggests optimal segments for campaigns
    - Provides segment analytics (growth rate, conversion rate)
    """

    def __init__(self, icp: Optional[Dict] = None):
        self.segments: Dict[str, Segment] = {}
        self.icp = icp or {}

        # Load default segments
        for seg in DEFAULT_SEGMENTS:
            self.segments[seg.id] = seg

    def create_segment(
        self,
        name: str,
        rules: List[Dict[str, Any]],
        logic: str = "and",
        description: str = "",
        segment_id: Optional[str] = None,
    ) -> Segment:
        """Create a new dynamic segment."""
        seg_id = segment_id or name.lower().replace(" ", "_")

        parsed_rules = []
        for rule in rules:
            parsed_rules.append(SegmentRule(
                field=rule["field"],
                operator=SegmentOperator(rule["operator"]),
                value=rule["value"],
                negate=rule.get("negate", False),
            ))

        segment = Segment(
            id=seg_id,
            name=name,
            description=description,
            rules=parsed_rules,
            logic=logic,
        )
        self.segments[seg_id] = segment
        return segment

    def evaluate_lead(self, lead: Dict[str, Any]) -> List[str]:
        """
        Evaluate which segments a lead belongs to.

        Returns list of segment IDs the lead qualifies for.
        """
        matching_segments = []

        for segment in self.segments.values():
            if self._lead_matches_segment(lead, segment):
                matching_segments.append(segment.id)

        return matching_segments

    def evaluate_batch(self, leads: List[Dict[str, Any]]) -> Dict[str, List[str]]:
        """Evaluate multiple leads against all segments."""
        results = {}
        for lead in leads:
            lead_id = lead.get("id", str(id(lead)))
            results[lead_id] = self.evaluate_lead(lead)
        return results

    def get_segment_members(
        self, segment_id: str, leads: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Get all leads that match a specific segment."""
        segment = self.segments.get(segment_id)
        if not segment:
            return []

        return [lead for lead in leads if self._lead_matches_segment(lead, segment)]

    def suggest_segments(self, leads: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        AI-powered segment suggestions based on lead data patterns.
        Analyzes clusters and common attributes.
        """
        suggestions = []

        # Analyze source distribution
        sources = {}
        for lead in leads:
            src = lead.get("source", "unknown")
            sources[src] = sources.get(src, 0) + 1

        for source, count in sources.items():
            if count >= 10:
                suggestions.append({
                    "name": f"Leads from {source.replace('_', ' ').title()}",
                    "description": f"{count} leads sourced from {source}",
                    "rules": [{"field": "source", "operator": "eq", "value": source}],
                    "member_count": count,
                    "recommendation": "Create targeted campaign for this source",
                })

        # Analyze score clusters
        hot = sum(1 for l in leads if (l.get("score") or 0) >= 75)
        warm = sum(1 for l in leads if 45 <= (l.get("score") or 0) < 75)
        cold = sum(1 for l in leads if (l.get("score") or 0) < 45)

        if hot > 0:
            suggestions.append({
                "name": "Ready to Buy",
                "description": f"{hot} leads scoring 75+, ready for direct outreach",
                "rules": [{"field": "score", "operator": "gte", "value": 75}],
                "member_count": hot,
                "recommendation": "Assign to sales reps immediately",
            })

        # Analyze job title patterns
        titles = {}
        for lead in leads:
            title = (lead.get("job_title") or "").lower()
            if "ceo" in title or "founder" in title:
                titles["founders"] = titles.get("founders", 0) + 1
            elif "cto" in title or "vp eng" in title or "engineering" in title:
                titles["technical_leaders"] = titles.get("technical_leaders", 0) + 1
            elif "marketing" in title or "cmo" in title:
                titles["marketing_leaders"] = titles.get("marketing_leaders", 0) + 1

        for title_group, count in titles.items():
            if count >= 5:
                suggestions.append({
                    "name": f"{title_group.replace('_', ' ').title()} Segment",
                    "description": f"{count} {title_group.replace('_', ' ')} in your pipeline",
                    "member_count": count,
                    "recommendation": f"Create persona-specific messaging for {title_group}",
                })

        # Geographic clusters
        countries = {}
        for lead in leads:
            country = lead.get("country")
            if country:
                countries[country] = countries.get(country, 0) + 1

        for country, count in countries.items():
            if count >= 10:
                suggestions.append({
                    "name": f"Leads in {country}",
                    "description": f"{count} leads located in {country}",
                    "rules": [{"field": "country", "operator": "eq", "value": country}],
                    "member_count": count,
                    "recommendation": "Consider timezone-aware campaigns",
                })

        # Engagement-based suggestions
        never_contacted = sum(1 for l in leads if not l.get("last_contacted_at"))
        if never_contacted > 20:
            suggestions.append({
                "name": "Never Contacted",
                "description": f"{never_contacted} leads never reached out to",
                "rules": [{"field": "last_contacted_at", "operator": "not_exists", "value": None}],
                "member_count": never_contacted,
                "recommendation": "Start with a welcome/intro campaign",
            })

        return suggestions

    def get_segment_analytics(
        self, segment_id: str, leads: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Get analytics for a segment."""
        members = self.get_segment_members(segment_id, leads)
        segment = self.segments.get(segment_id)

        if not segment or not members:
            return {"segment_id": segment_id, "member_count": 0}

        scores = [l.get("score", 0) for l in members]
        enriched = sum(1 for l in members if l.get("is_enriched"))
        contacted = sum(1 for l in members if l.get("last_contacted_at"))
        converted = sum(1 for l in members if l.get("status") == "converted")

        return {
            "segment_id": segment_id,
            "segment_name": segment.name,
            "member_count": len(members),
            "avg_score": round(sum(scores) / len(scores), 1) if scores else 0,
            "enriched_percentage": round(enriched / len(members) * 100, 1),
            "contacted_percentage": round(contacted / len(members) * 100, 1),
            "conversion_rate": round(converted / len(members) * 100, 2) if members else 0,
            "top_sources": self._get_top_values(members, "source", 5),
            "top_companies": self._get_top_values(members, "company_name", 5),
        }

    def _lead_matches_segment(self, lead: Dict[str, Any], segment: Segment) -> bool:
        """Check if a lead matches a segment's rules."""
        if not segment.rules:
            return False

        results = [self._evaluate_rule(lead, rule) for rule in segment.rules]

        if segment.logic == "and":
            return all(results)
        else:  # "or"
            return any(results)

    def _evaluate_rule(self, lead: Dict[str, Any], rule: SegmentRule) -> bool:
        """Evaluate a single rule against a lead."""
        value = lead.get(rule.field)
        result = False

        try:
            if rule.operator == SegmentOperator.EQUALS:
                result = value == rule.value
            elif rule.operator == SegmentOperator.NOT_EQUALS:
                result = value != rule.value
            elif rule.operator == SegmentOperator.GREATER_THAN:
                result = (value or 0) > rule.value
            elif rule.operator == SegmentOperator.GREATER_EQUAL:
                result = (value or 0) >= rule.value
            elif rule.operator == SegmentOperator.LESS_THAN:
                result = (value or 0) < rule.value
            elif rule.operator == SegmentOperator.LESS_EQUAL:
                result = (value or 0) <= rule.value
            elif rule.operator == SegmentOperator.CONTAINS:
                if isinstance(value, str):
                    result = rule.value.lower() in value.lower()
                elif isinstance(value, (list, set)):
                    result = rule.value in value
                elif isinstance(value, dict):
                    result = rule.value in str(value)
            elif rule.operator == SegmentOperator.NOT_CONTAINS:
                if isinstance(value, str):
                    result = rule.value.lower() not in value.lower()
                elif isinstance(value, (list, set)):
                    result = rule.value not in value
            elif rule.operator == SegmentOperator.STARTS_WITH:
                result = str(value or "").lower().startswith(str(rule.value).lower())
            elif rule.operator == SegmentOperator.ENDS_WITH:
                result = str(value or "").lower().endswith(str(rule.value).lower())
            elif rule.operator == SegmentOperator.IN:
                result = value in rule.value
            elif rule.operator == SegmentOperator.NOT_IN:
                result = value not in rule.value
            elif rule.operator == SegmentOperator.EXISTS:
                result = value is not None and value != "" and value != [] and value != {}
            elif rule.operator == SegmentOperator.NOT_EXISTS:
                result = value is None or value == "" or value == [] or value == {}
            elif rule.operator == SegmentOperator.BETWEEN:
                if isinstance(rule.value, (list, tuple)) and len(rule.value) == 2:
                    result = rule.value[0] <= (value or 0) <= rule.value[1]
            elif rule.operator == SegmentOperator.DAYS_AGO_LESS:
                if value and isinstance(value, datetime):
                    days = (datetime.utcnow() - value).days
                    result = days < rule.value
            elif rule.operator == SegmentOperator.DAYS_AGO_MORE:
                if value and isinstance(value, datetime):
                    days = (datetime.utcnow() - value).days
                    result = days > rule.value
                elif not value:
                    result = True  # Never active = infinite days ago
        except (TypeError, ValueError):
            result = False

        return not result if rule.negate else result

    def _get_top_values(self, leads: List[Dict], field: str, limit: int) -> List[Dict]:
        """Get top N values for a field."""
        counts: Dict[str, int] = {}
        for lead in leads:
            val = lead.get(field)
            if val:
                counts[str(val)] = counts.get(str(val), 0) + 1

        sorted_items = sorted(counts.items(), key=lambda x: x[1], reverse=True)
        return [{"value": k, "count": v} for k, v in sorted_items[:limit]]

    def list_segments(self) -> List[Dict[str, Any]]:
        """List all segments with basic info."""
        return [
            {
                "id": seg.id,
                "name": seg.name,
                "description": seg.description,
                "rules_count": len(seg.rules),
                "logic": seg.logic,
                "is_ai_generated": seg.is_ai_generated,
                "member_count": seg.member_count,
            }
            for seg in self.segments.values()
        ]
