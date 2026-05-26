"""Connector models - integrations with external systems."""
import enum
from sqlalchemy import Column, String, DateTime, Integer, Boolean, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from backend.database.base import Base
from backend.models.base import TimestampMixin


class ConnectorType(str, enum.Enum):
    HUBSPOT = "hubspot"
    SALESFORCE = "salesforce"
    GOOGLE_SHEETS = "google_sheets"
    CSV_IMPORT = "csv_import"
    WEBHOOK_INBOUND = "webhook_inbound"
    WEBHOOK_OUTBOUND = "webhook_outbound"
    SLACK = "slack"
    ZAPIER = "zapier"
    MAILCHIMP = "mailchimp"
    SENDGRID = "sendgrid"
    TWILIO = "twilio"
    CUSTOM_API = "custom_api"


class ConnectorStatus(str, enum.Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"
    SYNCING = "syncing"


class Connector(TimestampMixin, Base):
    __tablename__ = "connectors"

    name = Column(String(255), nullable=False)
    connector_type = Column(String(50), nullable=False, index=True)
    status = Column(String(20), default=ConnectorStatus.INACTIVE)
    description = Column(Text)

    # Auth & config
    credentials = Column(JSONB, default={})  # encrypted in production
    config = Column(JSONB, default={})
    """
    Config examples:
    HubSpot: {"sync_contacts": true, "sync_deals": true, "sync_interval_minutes": 30}
    Google Sheets: {"spreadsheet_id": "...", "sheet_name": "...", "header_row": 1}
    Webhook: {"url": "...", "secret": "...", "events": ["lead.created", "lead.scored"]}
    """

    # Sync metadata
    last_sync_at = Column(DateTime)
    last_sync_status = Column(String(20))
    last_sync_records = Column(Integer, default=0)
    total_records_synced = Column(Integer, default=0)
    sync_errors = Column(JSONB, default=[])

    # Mapping (how external fields map to our lead fields)
    field_mapping = Column(JSONB, default={})
    """
    Example: {"external_email": "email", "external_name": "first_name", "company": "company_name"}
    """

    # Ownership
    team_id = Column(UUID(as_uuid=True), ForeignKey("teams.id"), nullable=False)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))

    # Relationships
    team = relationship("Team", back_populates="connectors")
    syncs = relationship("ConnectorSync", back_populates="connector", cascade="all, delete-orphan")


class ConnectorSync(TimestampMixin, Base):
    __tablename__ = "connector_syncs"

    connector_id = Column(UUID(as_uuid=True), ForeignKey("connectors.id"), nullable=False)
    direction = Column(String(10), default="inbound")  # inbound, outbound
    status = Column(String(20), default="running")  # running, completed, failed
    records_processed = Column(Integer, default=0)
    records_created = Column(Integer, default=0)
    records_updated = Column(Integer, default=0)
    records_failed = Column(Integer, default=0)
    error_log = Column(JSONB, default=[])
    started_at = Column(DateTime)
    completed_at = Column(DateTime)

    # Relationships
    connector = relationship("Connector", back_populates="syncs")
