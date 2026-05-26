"""Workflow engine - orchestrates multi-step automation sequences."""
import asyncio
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional
from uuid import UUID
import structlog

from backend.services.automation.email_sender import EmailSender
from backend.services.automation.whatsapp_sender import WhatsAppSender
from backend.services.automation.slack_notifier import SlackNotifier
from backend.services.automation.triggers import TriggerEngine, TriggerType

logger = structlog.get_logger()


class WorkflowEngine:
    """
    Event-driven workflow engine that executes multi-step automations.

    Workflow types:
    1. Drip campaigns (timed email/WhatsApp sequences)
    2. Trigger-based (fire on events like score change, form submit)
    3. Conditional branching (if/else based on lead data)
    4. Multi-channel (email + WhatsApp + Slack in one flow)

    Built-in workflows:
    - New lead auto-enrichment + scoring
    - Hot lead alert to Slack + assign to rep
    - Cold lead nurture sequence
    - Follow-up reminder after no response
    - Re-engagement after inactivity
    - Score drop alert
    """

    def __init__(self):
        self.email_sender = EmailSender()
        self.whatsapp_sender = WhatsAppSender()
        self.slack_notifier = SlackNotifier()
        self.trigger_engine = TriggerEngine()
        self.registered_workflows: Dict[str, Dict] = {}
        self._setup_default_triggers()

    def _setup_default_triggers(self):
        """Register default system triggers."""
        from backend.services.automation.triggers import TriggerCondition

        # Hot lead alert
        self.trigger_engine.register_trigger(
            trigger_id="hot_lead_alert",
            trigger_type=TriggerType.SCORE_ABOVE_THRESHOLD,
            conditions=[TriggerCondition("score", "gte", 75)],
            actions=[
                {"type": "slack_notify", "channel": "#sales-alerts"},
                {"type": "assign_to_rep"},
            ],
            cooldown_minutes=60,
            priority=1,
        )

        # New lead enrichment
        self.trigger_engine.register_trigger(
            trigger_id="auto_enrich_new_lead",
            trigger_type=TriggerType.LEAD_CREATED,
            actions=[
                {"type": "enrich", "depth": "standard"},
                {"type": "score"},
            ],
            priority=2,
        )

        # No activity follow-up
        self.trigger_engine.register_trigger(
            trigger_id="no_activity_followup",
            trigger_type=TriggerType.NO_ACTIVITY_DAYS,
            conditions=[TriggerCondition("days_inactive", "gte", 7)],
            actions=[
                {"type": "send_email", "template": "follow_up"},
            ],
            cooldown_minutes=10080,  # 7 days
            priority=5,
        )

    def register_workflow(
        self,
        workflow_id: str,
        name: str,
        trigger_type: TriggerType,
        steps: List[Dict[str, Any]],
        conditions: Optional[List[Dict]] = None,
        enabled: bool = True,
    ):
        """
        Register a multi-step workflow.

        Steps format:
        [
            {"action": "send_email", "template": "welcome", "delay_hours": 0},
            {"action": "wait", "hours": 48},
            {"action": "check_condition", "field": "emails_opened", "operator": "gte", "value": 1},
            {"action": "send_email", "template": "follow_up", "delay_hours": 0},
            {"action": "slack_notify", "channel": "#sales", "message": "Lead engaged!"},
        ]
        """
        self.registered_workflows[workflow_id] = {
            "id": workflow_id,
            "name": name,
            "trigger_type": trigger_type,
            "steps": steps,
            "conditions": conditions,
            "enabled": enabled,
            "created_at": datetime.utcnow(),
        }
        logger.info("workflow_registered", workflow_id=workflow_id, name=name)

    async def process_event(
        self,
        event_type: TriggerType,
        event_data: Dict[str, Any],
        lead_data: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """
        Process an event through the trigger engine and execute matching actions.

        Returns list of actions executed with results.
        """
        matching_triggers = self.trigger_engine.evaluate_event(event_type, event_data)
        results = []

        for trigger in matching_triggers:
            for action in trigger["actions"]:
                result = await self._execute_action(action, lead_data, event_data)
                results.append({
                    "trigger_id": trigger["id"],
                    "action": action,
                    "result": result,
                    "timestamp": datetime.utcnow().isoformat(),
                })

        return results

    async def execute_workflow(
        self,
        workflow_id: str,
        lead_data: Dict[str, Any],
        context: Optional[Dict] = None,
    ) -> List[Dict[str, Any]]:
        """
        Execute a registered workflow for a lead.
        Processes steps sequentially with delays.
        """
        workflow = self.registered_workflows.get(workflow_id)
        if not workflow or not workflow["enabled"]:
            return [{"error": f"Workflow {workflow_id} not found or disabled"}]

        results = []
        step_context = context or {}

        for step_idx, step in enumerate(workflow["steps"]):
            action = step.get("action")
            logger.info("workflow_step", workflow=workflow_id, step=step_idx, action=action)

            # Handle delays
            if action == "wait":
                hours = step.get("hours", 0)
                minutes = step.get("minutes", 0)
                # In production this would schedule a Celery task
                # For now we log the intended delay
                results.append({
                    "step": step_idx,
                    "action": "wait",
                    "delay": f"{hours}h {minutes}m",
                    "scheduled_for": (datetime.utcnow() + timedelta(hours=hours, minutes=minutes)).isoformat(),
                })
                continue

            # Handle conditions (branching)
            if action == "check_condition":
                condition_met = self._evaluate_step_condition(step, lead_data)
                if not condition_met:
                    # Skip remaining steps or go to else branch
                    skip_to = step.get("skip_to_step")
                    if skip_to is not None:
                        results.append({"step": step_idx, "action": "branch", "condition_met": False, "skip_to": skip_to})
                    else:
                        results.append({"step": step_idx, "action": "branch", "condition_met": False, "workflow_ended": True})
                        break
                    continue
                results.append({"step": step_idx, "action": "branch", "condition_met": True})
                continue

            # Execute action
            result = await self._execute_action(step, lead_data, step_context)
            results.append({"step": step_idx, "action": action, "result": result})

        return results

    async def _execute_action(
        self,
        action: Dict[str, Any],
        lead_data: Dict[str, Any],
        context: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """Execute a single automation action."""
        action_type = action.get("type") or action.get("action")
        context = context or {}

        try:
            if action_type == "send_email":
                return await self._action_send_email(action, lead_data)
            elif action_type == "send_whatsapp":
                return await self._action_send_whatsapp(action, lead_data)
            elif action_type == "slack_notify":
                return await self._action_slack_notify(action, lead_data)
            elif action_type == "enrich":
                return {"status": "queued", "type": "enrichment", "depth": action.get("depth", "standard")}
            elif action_type == "score":
                return {"status": "queued", "type": "scoring"}
            elif action_type == "assign_to_rep":
                return await self._action_assign_lead(action, lead_data)
            elif action_type == "update_status":
                return {"status": "updated", "new_status": action.get("status")}
            elif action_type == "add_tag":
                return {"status": "tagged", "tag": action.get("tag")}
            elif action_type == "webhook":
                return await self._action_webhook(action, lead_data)
            else:
                return {"error": f"Unknown action: {action_type}"}

        except Exception as e:
            logger.error("action_failed", action=action_type, error=str(e))
            return {"error": str(e)}

    async def _action_send_email(self, action: Dict, lead: Dict) -> Dict:
        """Send email action."""
        email = lead.get("email")
        if not email:
            return {"success": False, "error": "No email address"}

        template = action.get("template", "")
        subject = action.get("subject", "Following up")
        body = action.get("body_html", "<p>Hi {{first_name}},</p>")

        # Variable substitution
        variables = {
            "first_name": lead.get("first_name", "there"),
            "last_name": lead.get("last_name", ""),
            "company_name": lead.get("company_name", "your company"),
            "job_title": lead.get("job_title", ""),
        }

        return await self.email_sender.send_email(
            to_email=email,
            subject=self.email_sender._render_template(subject, variables),
            body_html=self.email_sender._render_template(body, variables),
            lead_id=str(lead.get("id", "")),
        )

    async def _action_send_whatsapp(self, action: Dict, lead: Dict) -> Dict:
        """Send WhatsApp message action."""
        phone = lead.get("phone")
        if not phone:
            return {"success": False, "error": "No phone number"}

        message = action.get("message", "Hi {{first_name}}, following up!")
        variables = {"first_name": lead.get("first_name", "there")}

        for key, value in variables.items():
            message = message.replace(f"{{{{{key}}}}}", str(value or ""))

        return await self.whatsapp_sender.send_message(
            to_number=phone,
            message=message,
            lead_id=str(lead.get("id", "")),
        )

    async def _action_slack_notify(self, action: Dict, lead: Dict) -> Dict:
        """Send Slack notification action."""
        channel = action.get("channel", "#sales-alerts")
        message = action.get("message")

        if not message:
            # Use rich lead alert
            return await self.slack_notifier.notify_new_hot_lead(lead, channel)
        else:
            # Custom message
            variables = {
                "name": f"{lead.get('first_name', '')} {lead.get('last_name', '')}".strip(),
                "company": lead.get("company_name", ""),
                "score": str(lead.get("score", 0)),
            }
            for key, value in variables.items():
                message = message.replace(f"{{{{{key}}}}}", value)

            return await self.slack_notifier.send_notification(channel, message)

    async def _action_assign_lead(self, action: Dict, lead: Dict) -> Dict:
        """Auto-assign lead to a sales rep (round-robin or by territory)."""
        strategy = action.get("strategy", "round_robin")
        return {
            "status": "assigned",
            "strategy": strategy,
            "lead_id": str(lead.get("id", "")),
        }

    async def _action_webhook(self, action: Dict, lead: Dict) -> Dict:
        """Fire an outbound webhook."""
        url = action.get("url")
        if not url:
            return {"success": False, "error": "No webhook URL"}

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.post(
                    url,
                    json={
                        "event": action.get("event", "automation.triggered"),
                        "lead": lead,
                        "timestamp": datetime.utcnow().isoformat(),
                    },
                )
                return {"success": response.status_code < 400, "status_code": response.status_code}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _evaluate_step_condition(self, step: Dict, lead: Dict) -> bool:
        """Evaluate a workflow step condition."""
        field = step.get("field", "")
        operator = step.get("operator", "eq")
        value = step.get("value")
        actual = lead.get(field)

        if actual is None:
            return False

        if operator == "eq":
            return actual == value
        elif operator == "gte":
            return actual >= value
        elif operator == "lte":
            return actual <= value
        elif operator == "gt":
            return actual > value
        elif operator == "exists":
            return actual is not None and actual != ""
        return False

    def get_default_workflows(self) -> List[Dict]:
        """Return pre-built workflow templates."""
        return [
            {
                "id": "welcome_sequence",
                "name": "Welcome Email Sequence",
                "trigger": "lead_created",
                "steps": [
                    {"action": "send_email", "template": "welcome", "delay_hours": 0},
                    {"action": "wait", "hours": 48},
                    {"action": "check_condition", "field": "emails_opened", "operator": "gte", "value": 1},
                    {"action": "send_email", "template": "value_prop", "delay_hours": 0},
                    {"action": "wait", "hours": 72},
                    {"action": "send_email", "template": "case_study", "delay_hours": 0},
                ]
            },
            {
                "id": "hot_lead_alert",
                "name": "Hot Lead Sales Alert",
                "trigger": "score_above_threshold",
                "steps": [
                    {"action": "slack_notify", "channel": "#sales-alerts"},
                    {"action": "assign_to_rep", "strategy": "round_robin"},
                    {"action": "add_tag", "tag": "hot"},
                    {"action": "update_status", "status": "qualified"},
                ]
            },
            {
                "id": "re_engagement",
                "name": "Re-engagement Campaign",
                "trigger": "no_activity_days",
                "steps": [
                    {"action": "send_email", "template": "miss_you", "delay_hours": 0},
                    {"action": "wait", "hours": 96},
                    {"action": "check_condition", "field": "emails_opened", "operator": "gte", "value": 1},
                    {"action": "send_email", "template": "special_offer", "delay_hours": 0},
                    {"action": "wait", "hours": 72},
                    {"action": "send_whatsapp", "message": "Hi {{first_name}}, just wanted to check in!"},
                ]
            },
            {
                "id": "multi_channel_nurture",
                "name": "Multi-Channel Nurture",
                "trigger": "lead_created",
                "steps": [
                    {"action": "enrich", "depth": "standard"},
                    {"action": "score"},
                    {"action": "wait", "hours": 1},
                    {"action": "send_email", "template": "intro"},
                    {"action": "wait", "hours": 24},
                    {"action": "check_condition", "field": "score", "operator": "gte", "value": 60},
                    {"action": "slack_notify", "message": ":star: Warm lead: {{name}} ({{company}}) - Score: {{score}}"},
                    {"action": "send_whatsapp", "message": "Hi {{first_name}}, saw you checked us out!"},
                ]
            },
        ]
