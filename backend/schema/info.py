from pydantic import Field, HttpUrl
from typing import Optional
from .base import BaseSchema


class RentalInfo(BaseSchema):
    city : Optional[str] = Field(None, description="City of the rental property")
    area: Optional[str] = Field(None, description="Area or neighborhood of the rental property")
    price: Optional[float] = Field(None, gt=0)
    no_of_beds: Optional[int] = Field(None, ge=0)
    link: Optional[HttpUrl] = None