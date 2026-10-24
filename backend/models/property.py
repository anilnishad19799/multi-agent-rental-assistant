"""SQLAlchemy models for properties, configs, amenities, images, and landlord preferences."""
import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, Boolean, Float, Date, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from backend.models.base import Base


def _utcnow():
    return datetime.now(timezone.utc)


def _new_uuid():
    return str(uuid.uuid4())


class Property(Base):
    __tablename__ = "properties"

    id = Column(String, primary_key=True, default=_new_uuid)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    city = Column(String, nullable=False)
    area = Column(String, nullable=False)
    address = Column(String, nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    property_type = Column(String, nullable=False, default="PG")  # PG / FLAT
    gender_allowed = Column(String, nullable=True)  # MALE / FEMALE / ANY
    rating = Column(Float, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=_utcnow)

    # Relationships
    configs = relationship("PropertyConfig", back_populates="property", lazy="selectin")
    amenities = relationship("PropertyAmenity", back_populates="property", lazy="selectin")
    images = relationship("PropertyImage", back_populates="property", lazy="selectin")
    landlord_preferences = relationship("LandlordPreference", back_populates="property", lazy="selectin")


class PropertyConfig(Base):
    __tablename__ = "property_configs"

    id = Column(String, primary_key=True, default=_new_uuid)
    property_id = Column(String, ForeignKey("properties.id"), nullable=False)
    bhk_type = Column(String, nullable=True)
    total_beds = Column(Integer, nullable=True)
    available_beds = Column(Integer, nullable=True)
    sharing_type = Column(Integer, nullable=True)  # 2-sharing, 3-sharing, etc.
    rent = Column(Float, nullable=False)
    food_included = Column(Boolean, default=False)
    available_from = Column(Date, nullable=True)
    lease_min_months = Column(Integer, nullable=True)

    # Relationships
    property = relationship("Property", back_populates="configs")


class PropertyAmenity(Base):
    __tablename__ = "property_amenities"

    id = Column(String, primary_key=True, default=_new_uuid)
    property_id = Column(String, ForeignKey("properties.id"), nullable=False)
    amenity_name = Column(String, nullable=False)

    property = relationship("Property", back_populates="amenities")


class PropertyImage(Base):
    __tablename__ = "property_images"

    id = Column(String, primary_key=True, default=_new_uuid)
    property_id = Column(String, ForeignKey("properties.id"), nullable=False)
    image_url = Column(String, nullable=False)

    property = relationship("Property", back_populates="images")


class LandlordPreference(Base):
    __tablename__ = "landlord_preferences"

    id = Column(String, primary_key=True, default=_new_uuid)
    property_id = Column(String, ForeignKey("properties.id"), nullable=False)
    gender = Column(String, nullable=True)
    min_age = Column(Integer, nullable=True)
    max_age = Column(Integer, nullable=True)
    profession = Column(String, nullable=True)
    lease_required_months = Column(Integer, nullable=True)
    move_in_type = Column(String, nullable=True)
    no_cooking = Column(Boolean, default=False)
    no_visitors = Column(Boolean, default=False)

    property = relationship("Property", back_populates="landlord_preferences")
