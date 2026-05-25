"""Lead scoring models."""
from sqlalchemy import Column, String, Float, Integer, Boolean, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from backend.database.base import Base
from backend.models.base import TimestampMixin


class ScoringModel(TimestampMixin, Base):
    __tablename__ = "scoring_models"

    name = Column(String(255), nullable=False)
    description = Column(Text)
    version = Column(Integer, default=1)
    is_active = Column(Boolean, default=True)
    model_type = Column(String(50), default="weighted")  # weighted, ml, hybrid
    weights = Column(JSONB, default={})
    """
    Example weights:
    {
        "firmographic": {
            "company_size": 0.15,
            "industry_match": 0.20,
            "revenue_range": 0.10
        },
        "behavioral": {
            "email_opens": 0.10,
            "page_visits": 0.15,
            "form_submissions": 0.10
        },
        "engagement": {
            "response_rate": 0.10,
            "meeting_booked": 0.05,
            "content_downloads": 0.05
        }
    }
    """
    thresholds = Column(JSONB, default={
        "hot": 80,
        "warm": 50,
        "cold": 20
    })
    ml_model_path = Column(String(500))  # path to serialized ML model
    accuracy = Column(Float)
    team_id = Column(UUID(as_uuid=True), ForeignKey("teams.id"), nullable=False)


class LeadScore(TimestampMixin, Base):
    __tablename__ = "lead_scores"

    lead_id = Column(UUID(as_uuid=True), ForeignKey("leads.id"), nullable=False, index=True)
    model_id = Column(UUID(as_uuid=True), ForeignKey("scoring_models.id"), nullable=False)
    total_score = Column(Float, nullable=False)
    category = Column(String(20))  # hot, warm, cold
    breakdown = Column(JSONB, default={})
    """
    Example breakdown:
    {
        "firmographic_score": 35,
        "behavioral_score": 25,
        "engagement_score": 20,
        "intent_score": 10,
        "penalty": -5
    }
    """
    signals = Column(JSONB, default={})
    """
    Example signals:
    ["visited_pricing_page", "opened_3_emails", "company_hiring", "tech_match"]
    """

    # Relationships
    lead = relationship("Lead", back_populates="scores")
