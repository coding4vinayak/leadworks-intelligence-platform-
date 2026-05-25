"""Lead model - the core entity."""
import uuid
import enum
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Boolean, Float, Integer, ForeignKey, Text, Enum
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY
from sqlalchemy.orm import relationship
from backend.database.base import Base
from backend.models.base import TimestampMixin


class LeadStatus(str, enum.Enum):
    NEW = "new"
    CONTACTED = "contacted"
    QUALIFIED = "qualified"
    NURTURING = "nurturing"
    CONVERTED = "converted"
    LOST = "lost"
    SPAM = "spam"


class LeadSource(str, enum.Enum):
    MANUAL = "manual"
    WEB_FORM = "web_form"
    CSV_IMPORT = "csv_import"
    GOOGLE_SHEETS = "google_sheets"
    HUBSPOT = "hubspot"
    SALESFORCE = "salesforce"
    LINKEDIN_SCRAPE = "linkedin_scrape"
    WEBSITE_SCRAPE = "website_scrape"
    GOOGLE_MAPS_SCRAPE = "google_maps_scrape"
    API = "api"
    WEBHOOK = "webhook"
    EMAIL_FINDER = "email_finder"
    REFERRAL = "referral"


class Lead(TimestampMixin, Base):
    __tablename__ = "leads"

    # Basic info
    first_name = Column(String(100))
    last_name = Column(String(100))
    email = Column(String(255), index=True)
    phone = Column(String(50))
    job_title = Column(String(200))
    department = Column(String(100))
    linkedin_url = Column(String(500))
    twitter_url = Column(String(500))
    website = Column(String(500))
    avatar_url = Column(String(500))

    # Company association
    company_name = Column(String(255), index=True)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=True)

    # Location
    city = Column(String(100))
    state = Column(String(100))
    country = Column(String(100))
    timezone = Column(String(50))

    # Lead metadata
    status = Column(Enum(LeadStatus), default=LeadStatus.NEW, index=True)
    source = Column(Enum(LeadSource), default=LeadSource.MANUAL, index=True)
    source_detail = Column(String(500))  # e.g., specific form URL, import file name
    tags = Column(ARRAY(String), default=[])
    custom_fields = Column(JSONB, default={})

    # Scoring
    score = Column(Float, default=0.0, index=True)
    score_breakdown = Column(JSONB, default={})
    intent_signals = Column(JSONB, default={})

    # Engagement tracking
    last_contacted_at = Column(DateTime)
    last_responded_at = Column(DateTime)
    emails_sent = Column(Integer, default=0)
    emails_opened = Column(Integer, default=0)
    emails_clicked = Column(Integer, default=0)
    page_visits = Column(Integer, default=0)

    # Fraud detection
    is_spam = Column(Boolean, default=False)
    spam_score = Column(Float, default=0.0)
    fraud_flags = Column(JSONB, default={})

    # Enrichment status
    is_enriched = Column(Boolean, default=False)
    enriched_at = Column(DateTime)
    enrichment_sources = Column(ARRAY(String), default=[])

    # Ownership
    team_id = Column(UUID(as_uuid=True), ForeignKey("teams.id"), nullable=False)
    assigned_to = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    # Relationships
    company = relationship("Company", back_populates="leads")
    team = relationship("Team", back_populates="leads")
    enrichment_data = relationship("EnrichmentData", back_populates="lead", cascade="all, delete-orphan")
    scores = relationship("LeadScore", back_populates="lead", cascade="all, delete-orphan")
    activities = relationship("Activity", back_populates="lead", cascade="all, delete-orphan")
