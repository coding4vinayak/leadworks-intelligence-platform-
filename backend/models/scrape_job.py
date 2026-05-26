"""Scrape job model - tracks all scraping tasks."""
import enum
from sqlalchemy import Column, String, DateTime, Integer, Boolean, ForeignKey, Text, Float
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY
from sqlalchemy.orm import relationship
from backend.database.base import Base
from backend.models.base import TimestampMixin


class ScrapeJobStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RATE_LIMITED = "rate_limited"


class ScrapeJobType(str, enum.Enum):
    LINKEDIN_PROFILE = "linkedin_profile"
    LINKEDIN_COMPANY = "linkedin_company"
    LINKEDIN_SEARCH = "linkedin_search"
    GOOGLE_MAPS = "google_maps"
    WEBSITE = "website"
    EMAIL_FINDER = "email_finder"
    SOCIAL_MEDIA = "social_media"
    TECH_STACK = "tech_stack"
    NEWS = "news"
    WHOIS = "whois"
    CUSTOM_URL = "custom_url"


class ScrapeJob(TimestampMixin, Base):
    __tablename__ = "scrape_jobs"

    job_type = Column(String(50), nullable=False, index=True)
    status = Column(String(20), default=ScrapeJobStatus.PENDING, index=True)
    priority = Column(Integer, default=5)  # 1-10, 1 is highest

    # Input
    target_url = Column(String(2000))
    target_query = Column(String(500))
    input_params = Column(JSONB, default={})
    """
    Examples:
    LinkedIn search: {"keywords": "CTO SaaS", "location": "San Francisco", "page": 1}
    Google Maps: {"query": "marketing agencies NYC", "max_results": 50}
    Email finder: {"first_name": "John", "last_name": "Doe", "domain": "example.com"}
    Website: {"url": "https://example.com", "depth": 2, "extract": ["emails", "phones", "social"]}
    """

    # Output
    results_count = Column(Integer, default=0)
    results_data = Column(JSONB, default=[])
    extracted_leads = Column(Integer, default=0)

    # Execution metadata
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    duration_seconds = Column(Float)
    retry_count = Column(Integer, default=0)
    max_retries = Column(Integer, default=3)
    error_message = Column(Text)
    error_details = Column(JSONB, default={})

    # Rate limiting
    proxy_used = Column(String(200))
    requests_made = Column(Integer, default=0)

    # Ownership
    team_id = Column(UUID(as_uuid=True), ForeignKey("teams.id"), nullable=False)
    triggered_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    trigger_source = Column(String(50))  # manual, automation, enrichment, api
