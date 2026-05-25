"""Slack notifier - send alerts and updates to Slack channels."""
from datetime import datetime
from typing import Any, Dict, List, Optional
import httpx
import structlog

from backend.config import settings

logger = structlog.get_logger()


class SlackNotifier:
    """
    Slack notifications for lead events.

    Features:
    - Channel notifications (new hot lead, score change, etc.)
    - Direct messages to assigned sales reps
    - Rich message formatting with blocks
    - Interactive buttons (claim lead, view profile, snooze)
    - Threaded updates
    """

    def __init__(
        self,
        bot_token: Optional[str] = None,
        webhook_url: Optional[str] = None,
    ):
        self.bot_token = bot_token or settings.SLACK_BOT_TOKEN
        self.webhook_url = webhook_url or settings.SLACK_WEBHOOK_URL

    async def send_notification(
        self,
        channel: str,
        message: str,
        blocks: Optional[List[Dict]] = None,
        thread_ts: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Send a Slack message to a channel."""
        if not self.bot_token:
            return {"success": False, "error": "Slack bot token not configured"}

        try:
            async with httpx.AsyncClient() as client:
                payload = {
                    "channel": channel,
                    "text": message,
                }
                if blocks:
                    payload["blocks"] = blocks
                if thread_ts:
                    payload["thread_ts"] = thread_ts

                response = await client.post(
                    "https://slack.com/api/chat.postMessage",
                    headers={
                        "Authorization": f"Bearer {self.bot_token}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )

                data = response.json()
                if data.get("ok"):
                    return {"success": True, "ts": data.get("ts"), "channel": channel}
                else:
                    return {"success": False, "error": data.get("error")}

        except Exception as e:
            return {"success": False, "error": str(e)}

    async def send_webhook(self, message: str, blocks: Optional[List[Dict]] = None) -> Dict:
        """Send via incoming webhook (simpler, no auth needed)."""
        if not self.webhook_url:
            return {"success": False, "error": "Webhook URL not configured"}

        try:
            async with httpx.AsyncClient() as client:
                payload = {"text": message}
                if blocks:
                    payload["blocks"] = blocks

                response = await client.post(self.webhook_url, json=payload)
                return {"success": response.status_code == 200}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def build_new_lead_alert(self, lead: Dict[str, Any]) -> List[Dict]:
        """Build rich Slack blocks for a new hot lead alert."""
        name = f"{lead.get('first_name', '')} {lead.get('last_name', '')}".strip() or "Unknown"
        score = lead.get("score", 0)
        company = lead.get("company_name", "Unknown")
        title = lead.get("job_title", "")
        email = lead.get("email", "")
        source = lead.get("source", "")

        # Score emoji
        if score >= 75:
            score_emoji = ":fire:"
        elif score >= 45:
            score_emoji = ":star:"
        else:
            score_emoji = ":snowflake:"

        blocks = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": f"{score_emoji} New Lead: {name}"}
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Company:*\n{company}"},
                    {"type": "mrkdwn", "text": f"*Title:*\n{title}"},
                    {"type": "mrkdwn", "text": f"*Score:*\n{score}/100"},
                    {"type": "mrkdwn", "text": f"*Source:*\n{source}"},
                    {"type": "mrkdwn", "text": f"*Email:*\n{email}"},
                ]
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": ":hand: Claim Lead"},
                        "style": "primary",
                        "action_id": "claim_lead",
                        "value": str(lead.get("id", "")),
                    },
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": ":mag: View Profile"},
                        "action_id": "view_lead",
                        "value": str(lead.get("id", "")),
                    },
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": ":zzz: Snooze"},
                        "action_id": "snooze_lead",
                        "value": str(lead.get("id", "")),
                    },
                ]
            },
        ]
        return blocks

    def build_score_change_alert(self, lead: Dict, old_score: float, new_score: float) -> List[Dict]:
        """Build alert for significant score change."""
        name = f"{lead.get('first_name', '')} {lead.get('last_name', '')}".strip()
        direction = ":arrow_up:" if new_score > old_score else ":arrow_down:"

        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"{direction} *Score Change:* {name}\n"
                            f"Score: {old_score} → *{new_score}*\n"
                            f"Company: {lead.get('company_name', 'Unknown')}",
                }
            },
        ]
        return blocks

    def build_daily_summary(self, stats: Dict[str, Any]) -> List[Dict]:
        """Build daily summary report for Slack."""
        blocks = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": ":bar_chart: Daily Lead Summary"}
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*New Leads:*\n{stats.get('new_leads', 0)}"},
                    {"type": "mrkdwn", "text": f"*Hot Leads:*\n{stats.get('hot_leads', 0)}"},
                    {"type": "mrkdwn", "text": f"*Enriched:*\n{stats.get('enriched', 0)}"},
                    {"type": "mrkdwn", "text": f"*Emails Sent:*\n{stats.get('emails_sent', 0)}"},
                    {"type": "mrkdwn", "text": f"*Replies:*\n{stats.get('replies', 0)}"},
                    {"type": "mrkdwn", "text": f"*Conversions:*\n{stats.get('conversions', 0)}"},
                ]
            },
            {"type": "divider"},
            {
                "type": "context",
                "elements": [
                    {"type": "mrkdwn", "text": f"Report generated at {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}"}
                ]
            },
        ]
        return blocks

    async def notify_new_hot_lead(self, lead: Dict, channel: str = "#sales-alerts") -> Dict:
        """Send a hot lead alert to sales channel."""
        blocks = self.build_new_lead_alert(lead)
        name = f"{lead.get('first_name', '')} {lead.get('last_name', '')}".strip()
        return await self.send_notification(
            channel=channel,
            message=f":fire: New hot lead: {name} ({lead.get('company_name', '')})",
            blocks=blocks,
        )

    async def notify_score_change(
        self, lead: Dict, old_score: float, new_score: float, channel: str = "#sales-alerts"
    ) -> Dict:
        """Alert on significant score change."""
        blocks = self.build_score_change_alert(lead, old_score, new_score)
        return await self.send_notification(channel=channel, message="Score changed", blocks=blocks)
