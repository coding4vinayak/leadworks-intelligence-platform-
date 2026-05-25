"""Connector Manager - orchestrates all integrations."""
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID
import structlog

from backend.services.connectors.base import BaseConnector, SyncResult
from backend.services.connectors.hubspot import HubSpotConnector
from backend.services.connectors.salesforce import SalesforceConnector
from backend.services.connectors.google_sheets import GoogleSheetsConnector
from backend.services.connectors.csv_import import CSVImporter
from backend.services.connectors.webhook import WebhookConnector

logger = structlog.get_logger()


CONNECTOR_CLASSES = {
    "hubspot": HubSpotConnector,
    "salesforce": SalesforceConnector,
    "google_sheets": GoogleSheetsConnector,
    "csv_import": CSVImporter,
    "webhook_inbound": WebhookConnector,
    "webhook_outbound": WebhookConnector,
}


class ConnectorManager:
    """
    Manages all connector instances and sync operations.

    Features:
    - Create/configure connectors
    - Run scheduled syncs
    - Handle sync conflicts
    - Track sync history
    - Manage credentials securely
    """

    def __init__(self):
        self.active_connectors: Dict[str, BaseConnector] = {}

    def create_connector(
        self,
        connector_type: str,
        credentials: Dict[str, Any],
        config: Dict[str, Any] = None,
        field_mapping: Dict[str, str] = None,
        connector_id: Optional[str] = None,
    ) -> BaseConnector:
        """Create and register a connector instance."""
        cls = CONNECTOR_CLASSES.get(connector_type)
        if not cls:
            raise ValueError(f"Unknown connector type: {connector_type}")

        connector = cls(
            credentials=credentials,
            config=config or {},
            field_mapping=field_mapping,
        )

        if connector_id:
            self.active_connectors[connector_id] = connector

        return connector

    async def test_connector(self, connector_id: str) -> bool:
        """Test a connector's connection."""
        connector = self.active_connectors.get(connector_id)
        if not connector:
            return False
        return await connector.test_connection()

    async def run_sync(
        self,
        connector_id: str,
        direction: str = "inbound",
        since: Optional[datetime] = None,
        leads: Optional[List[Dict]] = None,
    ) -> SyncResult:
        """Run a sync operation on a connector."""
        connector = self.active_connectors.get(connector_id)
        if not connector:
            return SyncResult(
                success=False,
                errors=[{"message": f"Connector {connector_id} not found"}],
            )

        logger.info("sync_started", connector_id=connector_id, direction=direction)

        if direction == "inbound":
            result = await connector.sync_inbound(since=since)
        elif direction == "outbound":
            result = await connector.sync_outbound(leads or [])
        else:
            result = SyncResult(success=False, errors=[{"message": "Invalid direction"}])

        logger.info(
            "sync_completed",
            connector_id=connector_id,
            success=result.success,
            records=result.records_processed,
        )

        return result

    async def import_csv(
        self,
        file_content: bytes,
        filename: str,
        field_mapping: Optional[Dict[str, str]] = None,
        team_id: Optional[UUID] = None,
    ) -> SyncResult:
        """Import leads from a CSV/Excel file."""
        importer = CSVImporter(credentials={}, config={})
        result = await importer.import_file(
            file_content=file_content,
            filename=filename,
            field_mapping=field_mapping,
        )
        return result

    async def process_webhook(
        self,
        connector_id: str,
        payload: Dict[str, Any],
        headers: Optional[Dict[str, str]] = None,
        source_ip: Optional[str] = None,
    ) -> SyncResult:
        """Process an incoming webhook."""
        connector = self.active_connectors.get(connector_id)
        if not connector or not isinstance(connector, WebhookConnector):
            return SyncResult(
                success=False,
                errors=[{"message": "Webhook connector not found"}],
            )

        return await connector.process_webhook(
            payload=payload,
            headers=headers,
            source_ip=source_ip,
        )

    def get_available_connectors(self) -> List[Dict[str, Any]]:
        """List all available connector types with their configs."""
        return [
            {
                "type": "hubspot",
                "name": "HubSpot",
                "description": "Sync contacts, companies, and deals",
                "auth_type": "oauth2",
                "supports": ["inbound", "outbound"],
                "required_fields": ["access_token"],
            },
            {
                "type": "salesforce",
                "name": "Salesforce",
                "description": "Enterprise CRM with leads, contacts, opportunities",
                "auth_type": "oauth2",
                "supports": ["inbound", "outbound"],
                "required_fields": ["client_id", "client_secret", "username", "password"],
            },
            {
                "type": "google_sheets",
                "name": "Google Sheets",
                "description": "Import/export leads from spreadsheets",
                "auth_type": "oauth2",
                "supports": ["inbound", "outbound"],
                "required_fields": ["access_token"],
                "config_fields": ["spreadsheet_id", "sheet_name"],
            },
            {
                "type": "csv_import",
                "name": "CSV/Excel Import",
                "description": "Bulk import from CSV or Excel files",
                "auth_type": "none",
                "supports": ["inbound"],
                "required_fields": [],
            },
            {
                "type": "webhook_inbound",
                "name": "Inbound Webhook",
                "description": "Receive leads via HTTP POST (forms, Zapier, etc.)",
                "auth_type": "hmac",
                "supports": ["inbound"],
                "required_fields": [],
                "config_fields": ["webhook_secret"],
            },
            {
                "type": "webhook_outbound",
                "name": "Outbound Webhook",
                "description": "Send lead events to external URLs",
                "auth_type": "custom",
                "supports": ["outbound"],
                "required_fields": ["outbound_url"],
                "config_fields": ["events", "payload_template"],
            },
        ]
