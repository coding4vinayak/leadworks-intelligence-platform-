"""Enrichment data model - stores data gathered from various sources."""
import enum
from sqlalchemy import Column, String, DateTime, ForeignKey, Enum, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from backend.database.base import Base
from backend.models.base import TimestampMixin


class EnrichmentSource(str, enum.Enum):
    CLEARBIT = "clearbit"
    HUNTER_IO = "hunter_io"
    LINKEDIN_SCRAPE = "linkedin_scrape"
    WEBSITE_SCRAPE = "website_scrape"
    GOOGLE_SEARCH = "google_search"
    WHOIS = "whois"
    SOCIAL_MEDIA = "social_media"
    OPENAI = "openai"
    BUILTWITH = "builtwith"
    CRUNCHBASE = "crunchbase"
    CUSTOM_API = "custom_api"


class EnrichmentData(TimestampMixin, Base):
    __tablename__ = "enrichment_data"

    lead_id = Column(UUID(as_uuid=True), ForeignKey("leads.id"), nullable=False, index=True)
    source = Column(Enum(EnrichmentSource), nullable=False)
    data_type = Column(String(100))  # e.g., "company_info", "social_profile", "tech_stack"
    raw_data = Column(JSONB, default={})
    processed_data = Column(JSONB, default={})
    confidence_score = Column(String(10))  # low, medium, high
    is_verified = Column(String(10), default="false")
    notes = Column(Text)

    # Relationships
    lead = relationship("Lead", back_populates="enrichment_data")
