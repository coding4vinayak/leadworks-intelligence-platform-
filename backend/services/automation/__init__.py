"""Automation engine - event-driven workflows for lead nurturing."""
from backend.services.automation.workflow_engine import WorkflowEngine
from backend.services.automation.email_sender import EmailSender
from backend.services.automation.whatsapp_sender import WhatsAppSender
from backend.services.automation.slack_notifier import SlackNotifier
from backend.services.automation.triggers import TriggerEngine, TriggerType

__all__ = [
    "WorkflowEngine", "EmailSender", "WhatsAppSender",
    "SlackNotifier", "TriggerEngine", "TriggerType",
]
