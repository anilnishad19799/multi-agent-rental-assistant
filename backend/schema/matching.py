from typing import Dict, Any, Optional
from .base import BaseSchema


class MatchData(BaseSchema):
    match_score: Optional[float] = None
    preferences_match: Optional[Dict[str, Any]] = None
    notes: Optional[str] = None 