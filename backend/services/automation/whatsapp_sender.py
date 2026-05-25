"""WhatsApp sender via Twilio API."""
from datetime import datetime
from typing import Any, Dict, List, Optional
import httpx
import structlog

from backend.config import settings

logger = structlog.get_logger()


class WhatsAppSender:
    """
    WhatsApp messaging via Twilio API.

    Features:
    - Send template messages
    - Send free-form messages (within 24h window)
    - Media messages (images, documents)
    - Quick reply buttons
    - Message status tracking
    - Opt-in/opt-out management
    """

    TWILIO_API = "https://api.twilio.com/2010-04-01"

    def __init__(
        self,
        account_sid: Optional[str] = None,
        auth_token: Optional[str] = None,
        from_number: Optional[str] = None,
    ):
        self.account_sid = account_sid or settings.TWILIO_ACCOUNT_SID
        self.auth_token = auth_token or settings.TWILIO_AUTH_TOKEN
        self.from_number = from_number or settings.TWILIO_WHATSAPP_NUMBER

    async def send_message(
        self,
        to_number: str,
        message: str,
        media_url: Optional[str] = None,
        lead_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Send a WhatsApp message.

        Args:
            to_number: Recipient phone (E.164 format, e.g., +14155551234)
            message: Message text
            media_url: Optional media attachment URL
            lead_id: Associated lead ID for tracking
        """
        if not self.account_sid or not self.auth_token:
            return {"success": False, "error": "Twilio credentials not configured"}

        # Format numbers for WhatsApp
        from_wa = f"whatsapp:{self.from_number}"
        to_wa = f"whatsapp:{to_number}"

        try:
            async with httpx.AsyncClient() as client:
                url = f"{self.TWILIO_API}/Accounts/{self.account_sid}/Messages.json"

                data = {
                    "From": from_wa,
                    "To": to_wa,
                    "Body": message,
                }
                if media_url:
                    data["MediaUrl"] = media_url

                response = await client.post(
                    url,
                    data=data,
                    auth=(self.account_sid, self.auth_token),
                )

                if response.status_code == 201:
                    result = response.json()
                    logger.info("whatsapp_sent", to=to_number, sid=result.get("sid"))
                    return {
                        "success": True,
                        "message_sid": result.get("sid"),
                        "status": result.get("status"),
                        "lead_id": lead_id,
                        "sent_at": datetime.utcnow().isoformat(),
                    }
                else:
                    error = response.json().get("message", response.text)
                    logger.error("whatsapp_failed", to=to_number, error=error)
                    return {"success": False, "error": error}

        except Exception as e:
            logger.error("whatsapp_error", error=str(e))
            return {"success": False, "error": str(e)}

    async def send_template(
        self,
        to_number: str,
        template_sid: str,
        variables: Dict[str, str] = None,
        lead_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Send a pre-approved WhatsApp template message.
        Templates can be sent outside the 24h window.
        """
        if not self.account_sid:
            return {"success": False, "error": "Twilio not configured"}

        try:
            async with httpx.AsyncClient() as client:
                url = f"{self.TWILIO_API}/Accounts/{self.account_sid}/Messages.json"

                # Build content variables
                content_vars = {}
                if variables:
                    for i, (key, value) in enumerate(variables.items(), 1):
                        content_vars[str(i)] = value

                data = {
                    "From": f"whatsapp:{self.from_number}",
                    "To": f"whatsapp:{to_number}",
                    "ContentSid": template_sid,
                }
                if content_vars:
                    import json
                    data["ContentVariables"] = json.dumps(content_vars)

                response = await client.post(url, data=data, auth=(self.account_sid, self.auth_token))

                if response.status_code == 201:
                    result = response.json()
                    return {
                        "success": True,
                        "message_sid": result.get("sid"),
                        "lead_id": lead_id,
                    }
                else:
                    return {"success": False, "error": response.text}

        except Exception as e:
            return {"success": False, "error": str(e)}

    async def send_batch(
        self,
        recipients: List[Dict[str, Any]],
        message_template: str,
        delay_seconds: float = 2.0,
    ) -> List[Dict]:
        """
        Send messages to multiple recipients.

        Each recipient: {"phone": "+1...", "variables": {"first_name": "..."}, "lead_id": "..."}
        """
        import asyncio
        results = []

        for recipient in recipients:
            phone = recipient["phone"]
            variables = recipient.get("variables", {})

            # Render message
            message = message_template
            for key, value in variables.items():
                message = message.replace(f"{{{{{key}}}}}", str(value or ""))

            result = await self.send_message(
                to_number=phone,
                message=message,
                lead_id=recipient.get("lead_id"),
            )
            results.append(result)

            await asyncio.sleep(delay_seconds)

        return results
