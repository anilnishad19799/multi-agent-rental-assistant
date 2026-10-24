from datetime import datetime
from typing import Optional
from .base import BaseSchema
from .enums import BookStatus


class Booking(BaseSchema):
    book_date: datetime
    book_status: BookStatus = BookStatus.pending