"""User and Team models."""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Boolean, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from backend.database.base import Base
from backend.models.base import TimestampMixin


class Team(TimestampMixin, Base):
    __tablename__ = "teams"

    name = Column(String(255), nullable=False)
    slug = Column(String(100), unique=True, nullable=False)
    plan = Column(String(50), default="free")  # free, starter, pro, enterprise
    max_leads = Column(Integer, default=1000)
    max_enrichments_per_month = Column(Integer, default=500)
    max_scrape_jobs_per_month = Column(Integer, default=100)
    settings = Column(JSONB, default={})

    # Relationships
    users = relationship("User", back_populates="team")
    leads = relationship("Lead", back_populates="team")
    connectors = relationship("Connector", back_populates="team")
    campaigns = relationship("Campaign", back_populates="team")


class User(TimestampMixin, Base):
    __tablename__ = "users"

    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255))
    role = Column(String(50), default="member")  # owner, admin, member, viewer
    is_active = Column(Boolean, default=True)
    last_login = Column(DateTime)
    avatar_url = Column(String(500))

    # Foreign keys
    team_id = Column(UUID(as_uuid=True), ForeignKey("teams.id"), nullable=False)

    # Relationships
    team = relationship("Team", back_populates="users")
