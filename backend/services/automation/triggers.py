"""Event triggers - define when automations fire."""
import enum
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional
import structlog

logger = structlog.get_logger()


class TriggerType(str, enum.Enum):
    # Lead lifecycle
    LEAD_CREATED = "lead_created"
    LEAD_SCORED = "lead_scored"
    LEAD_ENRICHED = "lead_enriched"
    LEAD_STATUS_CHANGED = "lead_status_changed"
    LEAD_ASSIGNED = "lead_assigned"
    LEAD_TAG_ADDED = "lead_tag_added"

    # Score-based
    SCORE_ABOVE_THRESHOLD = "score_above_threshold"
    SCORE_DROPPED = "score_dropped"
    CATEGORY_CHANGED = "category_changed"

    # Engagement
    EMAIL_OPENED = "email_opened"
    EMAIL_CLICKED = "email_clicked"
    EMAIL_REPLIED = "email_replied"
    EMAIL_BOUNCED = "email_bounced"
    FORM_SUBMITTED = "form_submitted"
    PAGE_VISITED = "page_visited"
    MEETING_BOOKED = "meeting_booked"

    # Time-based
    NO_ACTIVITY_DAYS = "no_activity_days"
    FOLLOW_UP_DUE = "follow_up_due"
    SCHEDULED = "scheduled"

    # Connector
    CRM_DEAL_STAGE_CHANGED = "crm_deal_stage_changed"
    CONNECTOR_SYNC_COMPLETED = "connector_sync_completed"

    # Custom
    WEBHOOK_RECEIVED = "webhook_received"
    MANUAL = "manual"


class TriggerCondition:
    """Defines a condition that must be met for a trigger to fire."""

    def __init__(
        self,
        field: str,
        operator: str,
        value: Any,
    ):
        self.field = field
        self.operator = operator
        self.value = value

    def evaluate(self, data: Dict[str, Any]) -> bool:
        """Check if condition is met."""
        actual = data.get(self.field)
        if actual is None:
            return False

        if self.operator == "eq":
            return actual == self.value
        elif self.operator == "neq":
            return actual != self.value
        elif self.operator == "gt":
            return actual > self.value
        elif self.operator == "gte":
            return actual >= self.value
        elif self.operator == "lt":
            return actual < self.value
        elif self.operator == "lte":
            return actual <= self.value
        elif self.operator == "contains":
            return self.value in str(actual)
        elif self.operator == "in":
            return actual in self.value
        elif self.operator == "not_in":
            return actual not in self.value
        elif self.operator == "exists":
            return actual is not None and actual != ""
        elif self.operator == "not_exists":
            return actual is None or actual == ""
        return False


class TriggerEngine:
    """
    Evaluates events against registered triggers and fires matching workflows.

    Features:
    - Register triggers with conditions
    - Evaluate events in real-time
    - Support for compound conditions (AND/OR)
    - Cooldown periods (don't re-trigger too fast)
    - Priority-based execution
    """

    def __init__(self):
        self.registered_triggers: List[Dict] = []
        self.cooldowns: Dict[str, datetime] = {}

    def register_trigger(
        self,
        trigger_id: str,
        trigger_type: TriggerType,
        conditions: List[TriggerCondition] = None,
        condition_logic: str = "and",  # "and" or "or"
        workflow_id: str = None,
        actions: List[Dict] = None,
        cooldown_minutes: int = 0,
        priority: int = 5,
        enabled: bool = True,
    ):
        """Register a new trigger."""
        self.registered_triggers.append({
            "id": trigger_id,
            "type": trigger_type,
            "conditions": conditions or [],
            "condition_logic": condition_logic,
            "workflow_id": workflow_id,
            "actions": actions or [],
            "cooldown_minutes": cooldown_minutes,
            "priority": priority,
            "enabled": enabled,
        })

    def evaluate_event(
        self,
        event_type: TriggerType,
        event_data: Dict[str, Any],
    ) -> List[Dict]:
        """
        Evaluate an event against all registered triggers.
        Returns list of triggers that should fire.
        """
        matching_triggers = []

        for trigger in self.registered_triggers:
            if not trigger["enabled"]:
                continue
            if trigger["type"] != event_type:
                continue

            # Check cooldown
            trigger_id = trigger["id"]
            if trigger_id in self.cooldowns:
                cooldown_end = self.cooldowns[trigger_id]
                if datetime.utcnow() < cooldown_end:
                    continue

            # Evaluate conditions
            if self._check_conditions(trigger, event_data):
                matching_triggers.append(trigger)

                # Set cooldown
                if trigger["cooldown_minutes"] > 0:
                    self.cooldowns[trigger_id] = (
                        datetime.utcnow() + timedelta(minutes=trigger["cooldown_minutes"])
                    )

        # Sort by priority (lower = higher priority)
        matching_triggers.sort(key=lambda t: t["priority"])

        return matching_triggers

    def _check_conditions(self, trigger: Dict, data: Dict) -> bool:
        """Check if all/any conditions are met."""
        conditions = trigger["conditions"]
        if not conditions:
            return True  # No conditions = always fire

        results = [c.evaluate(data) for c in conditions]

        if trigger["condition_logic"] == "and":
            return all(results)
        else:  # "or"
            return any(results)
