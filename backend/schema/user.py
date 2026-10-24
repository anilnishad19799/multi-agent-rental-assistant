from pydantic import Field
from typing import Optional
from datetime import date
from .base import BaseSchema
from .enums import Gender, YesNo, PassType


class UserInfo(BaseSchema):
    name: str
    gender: Optional[Gender]
    working_profession: Optional[str]
    age: Optional[int] = Field(None, ge=18)
    citizenzip: Optional[str]
    lease_period: Optional[int] = Field(
        None, description="Lease duration in months"
    )
    move_in_date: Optional[date]
    number_of_person: Optional[int] = Field(None, ge=1)
    # landlord rules
    cooking_available: Optional[bool] = False

