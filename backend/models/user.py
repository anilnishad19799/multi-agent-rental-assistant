"""SQLAlchemy models for users and preferences."""
import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, Boolean, Float, Date, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from backend.models.base import Base


def _utcnow():
    return datetime.now(timezone.utc)


def _new_uuid():
    return str(uuid.uuid4())


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=_new_uuid)
    name = Column(String, nullable=True)
    gender = Column(String, nullable=True)
    age = Column(Integer, nullable=True)
    working_profession = Column(String, nullable=True)
    citizenship = Column(String, nullable=True)  # INDIAN / FOREIGN
    email = Column(String, nullable=True, unique=True)
    phone = Column(String, nullable=True)
    password_hash = Column(String, nullable=True)
    is_admin = Column(Boolean, default=False)
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    # Relationships
    preferences = relationship("UserPreference", back_populates="user", lazy="selectin")
    conversations = relationship("Conversation", back_populates="user", lazy="selectin")


class UserPreference(Base):
    __tablename__ = "user_preferences"

    id = Column(String, primary_key=True, default=_new_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    preferred_city = Column(String, nullable=True)
    preferred_area = Column(String, nullable=True)
    budget_max = Column(Float, nullable=True)
    required_beds = Column(Integer, nullable=True)
    sharing_types = Column(String, nullable=True)  # comma-separated: "2,3"
    lease_months = Column(Integer, nullable=True)
    move_in_date = Column(Date, nullable=True)
    number_of_people = Column(Integer, nullable=True)
    cooking_allowed = Column(Boolean, nullable=True)
    created_at = Column(DateTime, default=_utcnow)

    # Relationships
    user = relationship("User", back_populates="preferences")
