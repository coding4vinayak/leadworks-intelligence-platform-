"""Email sender - SMTP/API-based email delivery with templates and tracking."""
import asyncio
import uuid
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Dict, List, Optional
import httpx
import structlog

from backend.config import settings

logger = structlog.get_logger()


class EmailSender:
    """
    Email delivery service supporting:
    - SMTP sending
    - SendGrid/Mailgun API
    - Template rendering with variables
    - Open/click tracking pixel injection
    - Bounce handling
    - Unsubscribe management
    - Send scheduling (time zones, business hours)
    """

    def __init__(
        self,
        provider: str = "smtp",
        api_key: Optional[str] = None,
        from_email: Optional[str] = None,
        from_name: Optional[str] = None,
        tracking_domain: Optional[str] = None,
    ):
        self.provider = provider  # "smtp", "sendgrid", "mailgun"
        self.api_key = api_key
        self.from_email = from_email or settings.SMTP_USER or "noreply@leadworks.io"
        self.from_name = from_name or "Leadworks"
        self.tracking_domain = tracking_domain or "track.leadworks.io"

    async def send_email(
        self,
        to_email: str,
        subject: str,
        body_html: str,
        body_text: Optional[str] = None,
        reply_to: Optional[str] = None,
        cc: Optional[List[str]] = None,
        bcc: Optional[List[str]] = None,
        headers: Optional[Dict[str, str]] = None,
        track_opens: bool = True,
        track_clicks: bool = True,
        lead_id: Optional[str] = None,
        campaign_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Send a single email.

        Returns:
            {"success": bool, "message_id": str, "error": str}
        """
        # Generate tracking ID
        message_id = str(uuid.uuid4())

        # Inject tracking
        if track_opens:
            body_html = self._inject_open_tracker(body_html, message_id)
        if track_clicks:
            body_html = self._wrap_links(body_html, message_id)

        # Add unsubscribe header
        unsub_url = f"https://{self.tracking_domain}/unsubscribe/{message_id}"

        try:
            if self.provider == "sendgrid":
                result = await self._send_sendgrid(
                    to_email, subject, body_html, body_text,
                    reply_to, message_id, unsub_url,
                )
            elif self.provider == "mailgun":
                result = await self._send_mailgun(
                    to_email, subject, body_html, body_text,
                    reply_to, message_id, unsub_url,
                )
            else:
                result = await self._send_smtp(
                    to_email, subject, body_html, body_text,
                    reply_to, message_id,
                )

            result["message_id"] = message_id
            result["lead_id"] = lead_id
            result["campaign_id"] = campaign_id
            result["sent_at"] = datetime.utcnow().isoformat()

            logger.info("email_sent", to=to_email, message_id=message_id)
            return result

        except Exception as e:
            logger.error("email_send_failed", to=to_email, error=str(e))
            return {"success": False, "error": str(e), "message_id": message_id}

    async def send_batch(
        self,
        recipients: List[Dict[str, Any]],
        subject_template: str,
        body_html_template: str,
        body_text_template: Optional[str] = None,
        delay_seconds: float = 1.0,
    ) -> List[Dict]:
        """
        Send personalized emails to multiple recipients.

        Each recipient dict has: {"email": "...", "variables": {"first_name": "...", ...}}
        """
        results = []

        for recipient in recipients:
            email = recipient["email"]
            variables = recipient.get("variables", {})

            # Render templates
            subject = self._render_template(subject_template, variables)
            body_html = self._render_template(body_html_template, variables)
            body_text = self._render_template(body_text_template, variables) if body_text_template else None

            result = await self.send_email(
                to_email=email,
                subject=subject,
                body_html=body_html,
                body_text=body_text,
                lead_id=recipient.get("lead_id"),
                campaign_id=recipient.get("campaign_id"),
            )
            results.append(result)

            # Rate limit
            if delay_seconds > 0:
                await asyncio.sleep(delay_seconds)

        return results

    def _render_template(self, template: str, variables: Dict[str, Any]) -> str:
        """Render template with variable substitution."""
        rendered = template
        for key, value in variables.items():
            rendered = rendered.replace(f"{{{{{key}}}}}", str(value or ""))
            rendered = rendered.replace(f"{{{{ {key} }}}}", str(value or ""))
            rendered = rendered.replace(f"{{{key}}}", str(value or ""))
        return rendered

    def _inject_open_tracker(self, html: str, message_id: str) -> str:
        """Inject invisible tracking pixel."""
        pixel = f'<img src="https://{self.tracking_domain}/track/open/{message_id}" width="1" height="1" style="display:none" />'
        if "</body>" in html:
            return html.replace("</body>", f"{pixel}</body>")
        return html + pixel

    def _wrap_links(self, html: str, message_id: str) -> str:
        """Wrap links for click tracking."""
        import re
        pattern = r'href="(https?://[^"]+)"'

        def replace_link(match):
            original_url = match.group(1)
            # Don't track unsubscribe links
            if "unsubscribe" in original_url:
                return match.group(0)
            import urllib.parse
            encoded = urllib.parse.quote(original_url, safe='')
            tracked = f"https://{self.tracking_domain}/track/click/{message_id}?url={encoded}"
            return f'href="{tracked}"'

        return re.sub(pattern, replace_link, html)

    async def _send_smtp(self, to, subject, html, text, reply_to, message_id) -> Dict:
        """Send via SMTP (async wrapper)."""
        import aiosmtplib

        msg = MIMEMultipart("alternative")
        msg["From"] = f"{self.from_name} <{self.from_email}>"
        msg["To"] = to
        msg["Subject"] = subject
        msg["Message-ID"] = f"<{message_id}@leadworks.io>"
        if reply_to:
            msg["Reply-To"] = reply_to

        if text:
            msg.attach(MIMEText(text, "plain"))
        msg.attach(MIMEText(html, "html"))

        await aiosmtplib.send(
            msg,
            hostname=settings.SMTP_HOST or "localhost",
            port=settings.SMTP_PORT,
            username=settings.SMTP_USER,
            password=settings.SMTP_PASSWORD,
            use_tls=True,
        )

        return {"success": True, "provider": "smtp"}

    async def _send_sendgrid(self, to, subject, html, text, reply_to, msg_id, unsub_url) -> Dict:
        """Send via SendGrid API."""
        async with httpx.AsyncClient() as client:
            payload = {
                "personalizations": [{"to": [{"email": to}]}],
                "from": {"email": self.from_email, "name": self.from_name},
                "subject": subject,
                "content": [
                    {"type": "text/html", "value": html},
                ],
                "headers": {
                    "List-Unsubscribe": f"<{unsub_url}>",
                },
                "custom_args": {"message_id": msg_id},
            }

            if text:
                payload["content"].insert(0, {"type": "text/plain", "value": text})
            if reply_to:
                payload["reply_to"] = {"email": reply_to}

            response = await client.post(
                "https://api.sendgrid.com/v3/mail/send",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )

            return {"success": response.status_code in (200, 202), "provider": "sendgrid"}

    async def _send_mailgun(self, to, subject, html, text, reply_to, msg_id, unsub_url) -> Dict:
        """Send via Mailgun API."""
        domain = self.from_email.split("@")[1] if "@" in self.from_email else "leadworks.io"

        async with httpx.AsyncClient() as client:
            data = {
                "from": f"{self.from_name} <{self.from_email}>",
                "to": to,
                "subject": subject,
                "html": html,
                "h:List-Unsubscribe": unsub_url,
                "v:message_id": msg_id,
            }
            if text:
                data["text"] = text
            if reply_to:
                data["h:Reply-To"] = reply_to

            response = await client.post(
                f"https://api.mailgun.net/v3/{domain}/messages",
                auth=("api", self.api_key),
                data=data,
            )

            return {"success": response.status_code == 200, "provider": "mailgun"}
