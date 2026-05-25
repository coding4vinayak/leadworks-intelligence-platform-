"""Webhook connector - receive and send lead data via webhooks."""
import hashlib
import hmac
import json
from datetime import datetime
from typing import Any, Dict, List, Optional
import httpx
import structlog

from backend.services.connectors.base import BaseConnector, SyncResult

logger = structlog.get_logger()


class WebhookConnector(BaseConnector):
    """
    Webhook connector for real-time data sync:

    Inbound (receive):
    - Accept POST webhooks from any source (forms, Zapier, custom apps)
    - Verify webhook signatures (HMAC)
    - Parse various payload formats (JSON, form-data)
    - Map fields dynamically

    Outbound (send):
    - Send lead events to external URLs
    - Configurable event triggers
    - Retry logic with exponential backoff
    - Payload templates
    """

    @property
    def connector_type(self) -> str:
        return "webhook"

    def default_field_mapping(self) -> Dict[str, str]:
        return {
            "email": "email",
            "first_name": "first_name",
            "last_name": "last_name",
            "phone": "phone",
            "company": "company_name",
            "job_title": "job_title",
        }

    async def test_connection(self) -> bool:
        """Test outbound webhook URL if configured."""
        webhook_url = self.config.get("outbound_url")
        if not webhook_url:
            return True  # Inbound-only doesn't need testing

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.post(
                    webhook_url,
                    json={"event": "test", "timestamp": datetime.utcnow().isoformat()},
                    headers=self._get_outbound_headers(),
                )
                return response.status_code < 400
        except:
            return False

    async def sync_inbound(self, since: Optional[datetime] = None) -> SyncResult:
        """Not applicable - inbound webhooks are processed on-receive."""
        return SyncResult(success=True, metadata={"message": "Use process_webhook()"})

    def verify_signature(self, payload: bytes, signature: str) -> bool:
        """Verify HMAC webhook signature."""
        secret = self.credentials.get("webhook_secret", "").encode()
        if not secret:
            return True  # No secret configured, skip verification

        expected = hmac.new(secret, payload, hashlib.sha256).hexdigest()

        # Support various signature formats
        if signature.startswith("sha256="):
            signature = signature[7:]

        return hmac.compare_digest(expected, signature)

    async def process_webhook(
        self,
        payload: Dict[str, Any],
        headers: Optional[Dict[str, str]] = None,
        source_ip: Optional[str] = None,
    ) -> SyncResult:
        """
        Process an incoming webhook payload into a lead.

        Supports multiple payload formats:
        - Flat JSON: {"email": "...", "name": "..."}
        - Nested: {"data": {"contact": {"email": "..."}}}
        - Form builder format: {"fields": [{"name": "email", "value": "..."}]}
        - Zapier format: {"email": "...", "custom_fields": {...}}
        """
        result = SyncResult(success=True, direction="inbound", started_at=datetime.utcnow())

        try:
            # Normalize payload format
            normalized = self._normalize_payload(payload)

            if not normalized:
                result.success = False
                result.errors.append({"message": "Could not parse payload"})
                return result

            # Map to internal format
            mapped = self.map_fields(normalized, "inbound")
            mapped["source"] = "webhook"
            mapped["source_detail"] = self.config.get("name", "webhook")
            mapped["custom_fields"] = mapped.get("custom_fields", {})
            mapped["custom_fields"]["webhook_raw"] = payload
            mapped["custom_fields"]["source_ip"] = source_ip

            result.data = [mapped]
            result.records_created = 1
            result.records_processed = 1

        except Exception as e:
            result.success = False
            result.errors.append({"message": str(e)})

        result.completed_at = datetime.utcnow()
        return result

    def _normalize_payload(self, payload: Any) -> Optional[Dict]:
        """Normalize various webhook payload formats to flat dict."""
        if isinstance(payload, str):
            try:
                payload = json.loads(payload)
            except:
                return None

        if not isinstance(payload, dict):
            return None

        # Format 1: Already flat
        if "email" in payload:
            return payload

        # Format 2: Nested under 'data' or 'contact'
        for key in ["data", "contact", "lead", "submission", "entry"]:
            if key in payload and isinstance(payload[key], dict):
                return payload[key]

        # Format 3: Form fields array
        if "fields" in payload and isinstance(payload["fields"], list):
            flat = {}
            for field in payload["fields"]:
                name = field.get("name", field.get("label", ""))
                value = field.get("value", "")
                if name:
                    flat[name.lower().replace(" ", "_")] = value
            return flat if flat else None

        # Format 4: Form submissions (key-value pairs)
        if "form_data" in payload:
            return payload["form_data"]

        # Format 5: Check if it's a wrapper with useful nested data
        # Flatten one level
        flat = {}
        for key, value in payload.items():
            if isinstance(value, str) or isinstance(value, (int, float, bool)):
                flat[key] = value
            elif isinstance(value, dict):
                for k2, v2 in value.items():
                    flat[f"{key}_{k2}"] = v2

        return flat if flat else None

    async def sync_outbound(self, leads: List[Dict]) -> SyncResult:
        """Send lead data to outbound webhook URL."""
        result = SyncResult(success=True, direction="outbound", started_at=datetime.utcnow())

        webhook_url = self.config.get("outbound_url")
        if not webhook_url:
            result.success = False
            result.errors.append({"message": "No outbound URL configured"})
            return result

        events = self.config.get("events", ["lead.created"])

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                for lead in leads:
                    payload = self._build_outbound_payload(lead)

                    # Retry logic
                    max_retries = 3
                    for attempt in range(max_retries):
                        try:
                            response = await client.post(
                                webhook_url,
                                json=payload,
                                headers=self._get_outbound_headers(),
                            )

                            if response.status_code < 400:
                                result.records_created += 1
                                break
                            elif attempt < max_retries - 1:
                                import asyncio
                                await asyncio.sleep(2 ** attempt)
                            else:
                                result.records_failed += 1
                                result.errors.append({
                                    "email": lead.get("email"),
                                    "status": response.status_code,
                                })
                        except Exception as e:
                            if attempt == max_retries - 1:
                                result.records_failed += 1
                                result.errors.append({
                                    "email": lead.get("email"),
                                    "error": str(e),
                                })

                    result.records_processed += 1

        except Exception as e:
            result.success = False
            result.errors.append({"message": str(e)})

        result.completed_at = datetime.utcnow()
        return result

    def _build_outbound_payload(self, lead: Dict) -> Dict:
        """Build webhook payload from lead data."""
        template = self.config.get("payload_template")
        if template:
            # Use template with variable substitution
            payload = json.loads(json.dumps(template))
            for key, value in lead.items():
                placeholder = f"{{{key}}}"
                payload = json.loads(
                    json.dumps(payload).replace(placeholder, str(value or ""))
                )
            return payload
        else:
            # Default format
            return {
                "event": "lead.created",
                "timestamp": datetime.utcnow().isoformat(),
                "data": lead,
            }

    def _get_outbound_headers(self) -> Dict[str, str]:
        """Get headers for outbound webhook requests."""
        headers = {"Content-Type": "application/json"}

        # Add auth header if configured
        auth_type = self.config.get("auth_type")
        if auth_type == "bearer":
            headers["Authorization"] = f"Bearer {self.credentials.get('token', '')}"
        elif auth_type == "api_key":
            key_name = self.config.get("api_key_header", "X-API-Key")
            headers[key_name] = self.credentials.get("api_key", "")

        # Add custom headers
        custom_headers = self.config.get("custom_headers", {})
        headers.update(custom_headers)

        return headers
