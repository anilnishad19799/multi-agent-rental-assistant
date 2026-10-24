"""Pydantic output schemas for structured LLM responses.

Each agent has a typed schema that the LLM fills in.
These are passed to the LLM via structured_output / response_format,
guaranteeing valid, typed data that can flow directly to the database.
"""
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field


# ──────────────────────────────────────────────────────
# Supervisor Agent — routing decision
# ──────────────────────────────────────────────────────

class TargetAgentEnum(str, Enum):
    rent = "rent"
    user_info = "user_info"
    calendar = "calendar"
    general = "general"


class SupervisorDecision(BaseModel):
    """Structured routing decision from the Supervisor."""
    target_agent: TargetAgentEnum = Field(
        description="Which specialized agent should handle this query"
    )
    reasoning: str = Field(
        description="Brief explanation of why this agent was chosen"
    )
    extracted_intent: str = Field(
        description="What the user wants to do (e.g., property_search, greeting, book_appointment)"
    )


# ──────────────────────────────────────────────────────
# Rent Agent — search criteria extraction
# ──────────────────────────────────────────────────────

class RentExtraction(BaseModel):
    """Structured output for rental search criteria extracted from conversation."""
    city: Optional[str] = Field(None, description="City where user wants to rent")
    area: Optional[str] = Field(None, description="Specific area/neighborhood within the city")
    budget_max: Optional[float] = Field(None, description="Maximum rent budget in INR")
    beds: Optional[int] = Field(None, description="Number of beds needed")
    sharing_type: Optional[str] = Field(None, description="Sharing type, e.g. '2' for 2-sharing, '3' for 3-sharing")
    property_type: Optional[str] = Field("PG", description="PG or FLAT")
    food_included: Optional[bool] = Field(None, description="Whether food should be included")
    missing_fields: List[str] = Field(
        default_factory=list,
        description="List of field names that still need to be collected from the user"
    )


# ──────────────────────────────────────────────────────
# User Info Agent — user profile extraction
# ──────────────────────────────────────────────────────

class UserInfoExtraction(BaseModel):
    """Structured output for user personal information extracted from conversation."""
    name: Optional[str] = Field(None, description="User's full name")
    gender: Optional[str] = Field(None, description="Male, Female, or Other")
    working_profession: Optional[str] = Field(None, description="Job title or occupation")
    age: Optional[int] = Field(None, description="Age in years")
    citizenship: Optional[str] = Field(None, description="Indian or Foreign")
    lease_period: Optional[int] = Field(None, description="Desired lease duration in months")
    move_in_date: Optional[str] = Field(None, description="Desired move-in date in YYYY-MM-DD format")
    number_of_person: Optional[int] = Field(None, description="Total number of people who will stay")
    cooking_available: Optional[bool] = Field(None, description="Whether cooking facility is needed")
    missing_fields: List[str] = Field(
        default_factory=list,
        description="List of field names that still need to be collected from the user"
    )


# ──────────────────────────────────────────────────────
# Calendar Agent — booking action extraction
# ──────────────────────────────────────────────────────

class CalendarActionEnum(str, Enum):
    check_availability = "check_availability"
    suggest_slot = "suggest_slot"
    confirm_booking = "confirm_booking"
    ask_preference = "ask_preference"


class CalendarExtraction(BaseModel):
    """Structured output for appointment booking data."""
    action: CalendarActionEnum = Field(
        CalendarActionEnum.ask_preference,
        description="What action to take for booking"
    )
    date: Optional[str] = Field(None, description="Requested visit date in YYYY-MM-DD format")
    time: Optional[str] = Field(None, description="Requested visit time in HH:MM format")
    confirmed: bool = Field(False, description="Whether the user has confirmed the booking")
    property_id: Optional[str] = Field(None, description="ID of the property to visit")
    notes: Optional[str] = Field(None, description="Additional notes about the booking")
