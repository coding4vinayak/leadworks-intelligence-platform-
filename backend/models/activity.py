"""Activity tracking model."""
import enum
from sqlalchemy import Column, String, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from backend.database.base import Base
from backend.models.base import TimestampMixin


class ActivityType(str, enum.Enum):
    # Lead lifecycle
    LEAD_CREATED = "lead_created"
    LEAD_UPDATED = "lead_updated"
    LEAD_SCORED = "lead_scored"
    LEAD_ENRICHED = "lead_enriched"
    LEAD_STATUS_CHANGED = "lead_status_changed"
    LEAD_ASSIGNED = "lead_assigned"

    # Communication
    EMAIL_SENT = "email_sent"
    EMAIL_OPENED = "email_opened"
    EMAIL_CLICKED = "email_clicked"
    EMAIL_REPLIED = "email_replied"
    EMAIL_BOUNCED = "email_bounced"
    WHATSAPP_SENT = "whatsapp_sent"
    WHATSAPP_REPLIED = "whatsapp_replied"

    # Engagement
    PAGE_VISITED = "page_visited"
    FORM_SUBMITTED = "form_submitted"
    FILE_DOWNLOADED = "file_downloaded"
    MEETING_BOOKED = "meeting_booked"

    # Scraping & enrichment
    SCRAPE_COMPLETED = "scrape_completed"
    ENRICHMENT_COMPLETED = "enrichment_completed"

    # Fraud
    FRAUD_DETECTED = "fraud_detected"
    SPAM_FLAGGED = "spam_flagged"

    # System
    CONNECTOR_SYNCED = "connector_synced"
    CAMPAIGN_ENROLLED = "campaign_enrolled"
    AUTOMATION_TRIGGERED = "automation_triggered"


class Activity(TimestampMixin, Base):
    __tablename__ = "activities"

    lead_id = Column(UUID(as_uuid=True), ForeignKey("leads.id"), nullable=True, index=True)
    activity_type = Column(String(50), nullable=False, index=True)
    title = Column(String(500))
    description = Column(Text)
    metadata = Column(JSONB, default={})
    performed_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    ip_address = Column(String(50))
    user_agent = Column(String(500))

    # Relationships
    lead = relationship("Lead", back_populates="activities")
