"""SQLAlchemy models for search requests, results, bookings, and agent availability."""
import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, Boolean, Float, Date, Time, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from backend.models.base import Base


def _utcnow():
    return datetime.now(timezone.utc)


def _new_uuid():
    return str(uuid.uuid4())


class SearchRequest(Base):
    __tablename__ = "search_requests"

    id = Column(String, primary_key=True, default=_new_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=True)
    conversation_id = Column(String, nullable=True)
    city = Column(String, nullable=True)
    area = Column(String, nullable=True)
    budget_max = Column(Float, nullable=True)
    required_beds = Column(Integer, nullable=True)
    sharing_types = Column(String, nullable=True)
    created_at = Column(DateTime, default=_utcnow)

    results = relationship("SearchResult", back_populates="search_request", lazy="selectin")


class SearchResult(Base):
    __tablename__ = "search_results"

    id = Column(String, primary_key=True, default=_new_uuid)
    search_id = Column(String, ForeignKey("search_requests.id"), nullable=False)
    property_id = Column(String, ForeignKey("properties.id"), nullable=False)
    match_score = Column(Float, nullable=True)
    created_at = Column(DateTime, default=_utcnow)

    search_request = relationship("SearchRequest", back_populates="results")


class ShortlistedProperty(Base):
    __tablename__ = "shortlisted_properties"

    id = Column(String, primary_key=True, default=_new_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    property_id = Column(String, ForeignKey("properties.id"), nullable=False)
    created_at = Column(DateTime, default=_utcnow)


class Booking(Base):
    __tablename__ = "bookings"

    id = Column(String, primary_key=True, default=_new_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    property_id = Column(String, ForeignKey("properties.id"), nullable=False)
    visit_date = Column(Date, nullable=True)
    visit_time = Column(Time, nullable=True)
    status = Column(String, default="PENDING")  # PENDING / CONFIRMED / CANCELLED
    created_at = Column(DateTime, default=_utcnow)


class RealEstateAgent(Base):
    __tablename__ = "real_estate_agents"

    id = Column(String, primary_key=True, default=_new_uuid)
    name = Column(String, nullable=False)
    email = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    role = Column(String, nullable=True)

    availability = relationship("AgentAvailability", back_populates="agent", lazy="selectin")


class AgentAvailability(Base):
    __tablename__ = "agent_availability"

    id = Column(String, primary_key=True, default=_new_uuid)
    agent_id = Column(String, ForeignKey("real_estate_agents.id"), nullable=False)
    available_date = Column(Date, nullable=False)
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)
    is_booked = Column(Boolean, default=False)

    agent = relationship("RealEstateAgent", back_populates="availability")
