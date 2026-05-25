"""Campaign and automation models."""
import enum
from sqlalchemy import Column, String, DateTime, Integer, Boolean, ForeignKey, Text, Float
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY
from sqlalchemy.orm import relationship
from backend.database.base import Base
from backend.models.base import TimestampMixin


class CampaignStatus(str, enum.Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class StepType(str, enum.Enum):
    EMAIL = "email"
    WHATSAPP = "whatsapp"
    SLACK_ALERT = "slack_alert"
    WAIT = "wait"
    CONDITION = "condition"
    WEBHOOK = "webhook"
    ENRICH = "enrich"
    SCORE = "score"
    TAG = "tag"
    ASSIGN = "assign"


class Campaign(TimestampMixin, Base):
    __tablename__ = "campaigns"

    name = Column(String(255), nullable=False)
    description = Column(Text)
    status = Column(String(20), default=CampaignStatus.DRAFT)
    campaign_type = Column(String(50), default="drip")  # drip, trigger, one-shot

    # Targeting
    target_segment = Column(JSONB, default={})
    """
    Example: {"status": "new", "score_min": 50, "tags": ["saas"], "source": "linkedin_scrape"}
    """
    max_enrollments = Column(Integer, default=1000)
    enrolled_count = Column(Integer, default=0)

    # Schedule
    send_window_start = Column(String(5))  # "09:00"
    send_window_end = Column(String(5))  # "17:00"
    send_days = Column(ARRAY(String), default=["mon", "tue", "wed", "thu", "fri"])
    timezone = Column(String(50), default="UTC")

    # Metrics
    total_sent = Column(Integer, default=0)
    total_opened = Column(Integer, default=0)
    total_clicked = Column(Integer, default=0)
    total_replied = Column(Integer, default=0)
    total_converted = Column(Integer, default=0)
    conversion_rate = Column(Float, default=0.0)

    # Ownership
    team_id = Column(UUID(as_uuid=True), ForeignKey("teams.id"), nullable=False)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))

    # Relationships
    team = relationship("Team", back_populates="campaigns")
    steps = relationship("CampaignStep", back_populates="campaign", cascade="all, delete-orphan")
    enrollments = relationship("CampaignEnrollment", back_populates="campaign", cascade="all, delete-orphan")


class CampaignStep(TimestampMixin, Base):
    __tablename__ = "campaign_steps"

    campaign_id = Column(UUID(as_uuid=True), ForeignKey("campaigns.id"), nullable=False)
    step_order = Column(Integer, nullable=False)
    step_type = Column(String(30), nullable=False)
    name = Column(String(255))

    # Step config (varies by type)
    config = Column(JSONB, default={})
    """
    Email: {"subject": "...", "body_html": "...", "body_text": "..."}
    Wait: {"days": 3, "hours": 0}
    Condition: {"field": "score", "operator": "gte", "value": 70}
    WhatsApp: {"template": "...", "params": [...]}
    """

    # Delay before this step
    delay_days = Column(Integer, default=0)
    delay_hours = Column(Integer, default=0)

    # Metrics for this step
    sent_count = Column(Integer, default=0)
    opened_count = Column(Integer, default=0)
    clicked_count = Column(Integer, default=0)

    # Relationships
    campaign = relationship("Campaign", back_populates="steps")


class CampaignEnrollment(TimestampMixin, Base):
    __tablename__ = "campaign_enrollments"

    campaign_id = Column(UUID(as_uuid=True), ForeignKey("campaigns.id"), nullable=False)
    lead_id = Column(UUID(as_uuid=True), ForeignKey("leads.id"), nullable=False)
    current_step = Column(Integer, default=0)
    status = Column(String(20), default="active")  # active, completed, paused, exited
    enrolled_at = Column(DateTime)
    completed_at = Column(DateTime)
    exit_reason = Column(String(100))  # replied, converted, unsubscribed, bounced

    # Relationships
    campaign = relationship("Campaign", back_populates="enrollments")
