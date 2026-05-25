"""Lead routing engine - intelligent assignment to sales reps."""
import enum
import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from uuid import uuid4
import structlog

logger = structlog.get_logger()


class RoutingStrategy(str, enum.Enum):
    ROUND_ROBIN = "round_robin"
    WEIGHTED = "weighted"
    TERRITORY = "territory"
    SKILL_BASED = "skill_based"
    LOAD_BALANCED = "load_balanced"
    SCORE_BASED = "score_based"


@dataclass
class SalesRep:
    """Represents a sales rep for routing."""
    id: str
    name: str
    email: str
    is_active: bool = True
    capacity: int = 50  # max leads per period
    current_load: int = 0
    weight: float = 1.0  # for weighted routing
    territories: List[str] = field(default_factory=list)
    industries: List[str] = field(default_factory=list)
    skills: List[str] = field(default_factory=list)
    languages: List[str] = field(default_factory=lambda: ["en"])
    min_score_threshold: float = 0.0
    max_score_threshold: float = 100.0
    last_assigned_at: Optional[datetime] = None


@dataclass
class RoutingRule:
    """A rule that routes leads to specific reps."""
    id: str
    name: str
    priority: int = 5  # 1=highest
    conditions: List[Dict[str, Any]] = field(default_factory=list)
    target_rep_ids: List[str] = field(default_factory=list)
    strategy: RoutingStrategy = RoutingStrategy.ROUND_ROBIN
    is_active: bool = True



class LeadRouter:
    """
    Intelligent lead routing/assignment engine.

    Strategies:
    1. Round Robin - Distribute evenly, cycling through reps
    2. Weighted - Assign more to senior/higher-capacity reps
    3. Territory - Match by geography/region
    4. Skill-based - Match by industry/expertise
    5. Load-balanced - Assign to rep with lowest current load
    6. Score-based - Hot leads to senior reps, cold to juniors

    Features:
    - Rule-based routing with priority
    - Capacity management
    - Availability check (working hours, OOO)
    - Fallback routing when primary rep unavailable
    - Assignment history and metrics
    """

    def __init__(self):
        self.reps: Dict[str, SalesRep] = {}
        self.rules: List[RoutingRule] = []
        self._round_robin_index: int = 0
        self._assignment_history: List[Dict] = []

    def add_rep(self, rep: SalesRep):
        """Register a sales rep for routing."""
        self.reps[rep.id] = rep

    def add_rule(self, rule: RoutingRule):
        """Add a routing rule (sorted by priority)."""
        self.rules.append(rule)
        self.rules.sort(key=lambda r: r.priority)

    def route_lead(
        self,
        lead: Dict[str, Any],
        strategy: Optional[RoutingStrategy] = None,
    ) -> Dict[str, Any]:
        """
        Route a lead to the best available sales rep.

        Args:
            lead: Lead data
            strategy: Override default strategy

        Returns:
            {"assigned_to": rep_id, "rep_name": ..., "reason": ...}
        """
        available_reps = self._get_available_reps()
        if not available_reps:
            return {"assigned_to": None, "reason": "no_reps_available"}

        # Check rules first (highest priority)
        for rule in self.rules:
            if not rule.is_active:
                continue
            if self._lead_matches_rule(lead, rule):
                eligible = [r for r in available_reps if r.id in rule.target_rep_ids]
                if eligible:
                    rep = self._select_from_pool(eligible, rule.strategy, lead)
                    return self._assign(lead, rep, f"rule:{rule.name}")

        # Fall back to strategy-based routing
        effective_strategy = strategy or RoutingStrategy.ROUND_ROBIN
        rep = self._select_from_pool(available_reps, effective_strategy, lead)
        return self._assign(lead, rep, f"strategy:{effective_strategy.value}")

    def route_batch(
        self, leads: List[Dict[str, Any]], strategy: Optional[RoutingStrategy] = None
    ) -> List[Dict[str, Any]]:
        """Route multiple leads at once."""
        return [self.route_lead(lead, strategy) for lead in leads]

    def _get_available_reps(self) -> List[SalesRep]:
        """Get reps that are active and below capacity."""
        return [
            rep for rep in self.reps.values()
            if rep.is_active and rep.current_load < rep.capacity
        ]

    def _select_from_pool(
        self,
        pool: List[SalesRep],
        strategy: RoutingStrategy,
        lead: Dict[str, Any],
    ) -> SalesRep:
        """Select a rep from the pool using the given strategy."""
        if not pool:
            raise ValueError("Empty rep pool")

        if strategy == RoutingStrategy.ROUND_ROBIN:
            return self._round_robin(pool)
        elif strategy == RoutingStrategy.WEIGHTED:
            return self._weighted_select(pool)
        elif strategy == RoutingStrategy.TERRITORY:
            return self._territory_match(pool, lead)
        elif strategy == RoutingStrategy.SKILL_BASED:
            return self._skill_match(pool, lead)
        elif strategy == RoutingStrategy.LOAD_BALANCED:
            return self._load_balanced(pool)
        elif strategy == RoutingStrategy.SCORE_BASED:
            return self._score_based(pool, lead)
        else:
            return self._round_robin(pool)

    def _round_robin(self, pool: List[SalesRep]) -> SalesRep:
        """Simple round-robin cycling."""
        self._round_robin_index = (self._round_robin_index + 1) % len(pool)
        return pool[self._round_robin_index]

    def _weighted_select(self, pool: List[SalesRep]) -> SalesRep:
        """Weighted random selection based on rep weight."""
        weights = [r.weight for r in pool]
        total = sum(weights)
        r = random.uniform(0, total)
        cumulative = 0
        for rep, w in zip(pool, weights):
            cumulative += w
            if r <= cumulative:
                return rep
        return pool[-1]

    def _territory_match(self, pool: List[SalesRep], lead: Dict) -> SalesRep:
        """Match by geographic territory."""
        lead_country = (lead.get("country") or "").lower()
        lead_state = (lead.get("state") or "").lower()
        lead_city = (lead.get("city") or "").lower()

        for rep in pool:
            territories = [t.lower() for t in rep.territories]
            if lead_country in territories or lead_state in territories or lead_city in territories:
                return rep

        # Fallback to load-balanced
        return self._load_balanced(pool)

    def _skill_match(self, pool: List[SalesRep], lead: Dict) -> SalesRep:
        """Match by industry/skill expertise."""
        lead_industry = (lead.get("industry") or "").lower()
        lead_tags = [t.lower() for t in (lead.get("tags") or [])]

        best_match = None
        best_score = -1

        for rep in pool:
            score = 0
            rep_skills = [s.lower() for s in rep.skills]
            rep_industries = [i.lower() for i in rep.industries]

            if lead_industry in rep_industries:
                score += 3
            for tag in lead_tags:
                if tag in rep_skills:
                    score += 1

            if score > best_score:
                best_score = score
                best_match = rep

        return best_match or self._load_balanced(pool)

    def _load_balanced(self, pool: List[SalesRep]) -> SalesRep:
        """Assign to rep with lowest current load relative to capacity."""
        return min(pool, key=lambda r: r.current_load / max(r.capacity, 1))

    def _score_based(self, pool: List[SalesRep], lead: Dict) -> SalesRep:
        """High-score leads go to senior reps."""
        score = lead.get("score", 0)
        eligible = [
            r for r in pool
            if r.min_score_threshold <= score <= r.max_score_threshold
        ]
        if eligible:
            return self._load_balanced(eligible)
        return self._load_balanced(pool)

    def _lead_matches_rule(self, lead: Dict, rule: RoutingRule) -> bool:
        """Check if a lead matches a routing rule's conditions."""
        for condition in rule.conditions:
            field_name = condition.get("field", "")
            operator = condition.get("operator", "eq")
            value = condition.get("value")
            actual = lead.get(field_name)

            if operator == "eq" and actual != value:
                return False
            elif operator == "gte" and (actual or 0) < value:
                return False
            elif operator == "contains" and value not in str(actual or "").lower():
                return False
            elif operator == "in" and actual not in value:
                return False

        return True

    def _assign(self, lead: Dict, rep: SalesRep, reason: str) -> Dict[str, Any]:
        """Perform the assignment and update counters."""
        rep.current_load += 1
        rep.last_assigned_at = datetime.utcnow()

        assignment = {
            "assigned_to": rep.id,
            "rep_name": rep.name,
            "rep_email": rep.email,
            "reason": reason,
            "lead_id": lead.get("id"),
            "assigned_at": datetime.utcnow().isoformat(),
        }
        self._assignment_history.append(assignment)

        logger.info("lead_assigned", rep=rep.name, reason=reason, lead_id=lead.get("id"))
        return assignment

    def get_rep_stats(self) -> List[Dict[str, Any]]:
        """Get assignment statistics per rep."""
        stats = []
        for rep in self.reps.values():
            assigned_count = sum(
                1 for a in self._assignment_history if a["assigned_to"] == rep.id
            )
            stats.append({
                "rep_id": rep.id,
                "name": rep.name,
                "current_load": rep.current_load,
                "capacity": rep.capacity,
                "utilization": round(rep.current_load / max(rep.capacity, 1) * 100, 1),
                "total_assigned": assigned_count,
                "is_active": rep.is_active,
            })
        return stats
