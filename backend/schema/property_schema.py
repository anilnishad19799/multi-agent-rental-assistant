"""Pydantic schemas for property search."""
from pydantic import BaseModel
from typing import Optional, List


class SearchCriteriaSchema(BaseModel):
    city: Optional[str] = None
    area: Optional[str] = None
    budget_max: Optional[float] = None
    required_beds: Optional[int] = None
    sharing_types: Optional[str] = None
    property_type: Optional[str] = None


class PropertyListingSchema(BaseModel):
    id: str
    title: str
    description: Optional[str] = None
    city: str
    area: str
    address: Optional[str] = None
    property_type: str
    rent: float
    sharing_type: int
    available_beds: int
    food_included: bool
    rating: Optional[float] = None
    amenities: List[str] = []
    images: List[str] = []


class SearchResultsResponse(BaseModel):
    search_id: str
    criteria: SearchCriteriaSchema
    results: List[PropertyListingSchema]
    total_count: int
