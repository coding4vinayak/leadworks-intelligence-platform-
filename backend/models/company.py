"""Company model for B2B lead intelligence."""
from sqlalchemy import Column, String, Integer, Float, Boolean
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY
from sqlalchemy.orm import relationship
from backend.database.base import Base
from backend.models.base import TimestampMixin


class Company(TimestampMixin, Base):
    __tablename__ = "companies"

    # Basic info
    name = Column(String(255), nullable=False, index=True)
    domain = Column(String(255), unique=True, index=True)
    website = Column(String(500))
    logo_url = Column(String(500))
    description = Column(String(2000))
    industry = Column(String(200), index=True)
    sub_industry = Column(String(200))

    # Size & financials
    employee_count = Column(Integer)
    employee_range = Column(String(50))  # "1-10", "11-50", "51-200", etc.
    annual_revenue = Column(Float)
    revenue_range = Column(String(50))
    funding_total = Column(Float)
    funding_stage = Column(String(50))  # seed, series_a, series_b, etc.

    # Location
    headquarters_city = Column(String(100))
    headquarters_state = Column(String(100))
    headquarters_country = Column(String(100))
    address = Column(String(500))

    # Social & web
    linkedin_url = Column(String(500))
    twitter_url = Column(String(500))
    facebook_url = Column(String(500))
    crunchbase_url = Column(String(500))
    github_url = Column(String(500))

    # Tech intelligence
    tech_stack = Column(ARRAY(String), default=[])
    keywords = Column(ARRAY(String), default=[])
    sic_codes = Column(ARRAY(String), default=[])
    naics_codes = Column(ARRAY(String), default=[])

    # Enrichment
    is_enriched = Column(Boolean, default=False)
    enrichment_data = Column(JSONB, default={})

    # ICP (Ideal Customer Profile) scoring
    icp_score = Column(Float, default=0.0)

    # Relationships
    leads = relationship("Lead", back_populates="company")
