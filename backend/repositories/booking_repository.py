"""Booking repository — search requests, results, bookings, agent availability."""
import logging
from typing import List, Optional
from datetime import date, time
from sqlalchemy import select, and_
from backend.models.base import get_session
from backend.models import (
    SearchRequest, SearchResult, ShortlistedProperty,
    Booking, AgentAvailability, RealEstateAgent,
)
from backend.repositories.base_repository import BaseRepository

logger = logging.getLogger(__name__)


class BookingRepository(BaseRepository[Booking]):

    def __init__(self):
        super().__init__(Booking)

    async def create_search_request(self, **kwargs) -> SearchRequest:
        async with get_session() as session:
            sr = SearchRequest(**kwargs)
            session.add(sr)
            await session.commit()
            await session.refresh(sr)
            return sr

    async def save_search_results(
        self, search_id: str, results: List[dict]
    ) -> List[SearchResult]:
        """Save a list of search results: [{"property_id": ..., "match_score": ...}, ...]"""
        saved = []
        async with get_session() as session:
            for r in results:
                sr = SearchResult(
                    search_id=search_id,
                    property_id=r["property_id"],
                    match_score=r.get("match_score", 0.0),
                )
                session.add(sr)
                saved.append(sr)
            await session.commit()
        return saved

    async def shortlist_property(self, user_id: str, property_id: str) -> ShortlistedProperty:
        async with get_session() as session:
            sp = ShortlistedProperty(user_id=user_id, property_id=property_id)
            session.add(sp)
            await session.commit()
            await session.refresh(sp)
            return sp

    async def get_agent_availability(
        self, agent_id: str, target_date: date
    ) -> List[AgentAvailability]:
        async with get_session() as session:
            stmt = select(AgentAvailability).where(
                and_(
                    AgentAvailability.agent_id == agent_id,
                    AgentAvailability.available_date == target_date,
                    AgentAvailability.is_booked == False,
                )
            )
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def book_appointment(
        self, user_id: str, property_id: str,
        visit_date: date, visit_time: time
    ) -> Booking:
        async with get_session() as session:
            booking = Booking(
                user_id=user_id,
                property_id=property_id,
                visit_date=visit_date,
                visit_time=visit_time,
                status="PENDING",
            )
            session.add(booking)
            await session.commit()
            await session.refresh(booking)
            logger.info(f"Created booking {booking.id} for user {user_id}")
            return booking

    async def confirm_booking(self, booking_id: str) -> Optional[Booking]:
        async with get_session() as session:
            booking = await session.get(Booking, booking_id)
            if booking:
                booking.status = "CONFIRMED"
                await session.commit()
                await session.refresh(booking)
            return booking

    async def get_bookings_by_user(self, user_id: str) -> List[Booking]:
        async with get_session() as session:
            stmt = select(Booking).where(Booking.user_id == user_id)
            result = await session.execute(stmt)
            return list(result.scalars().all())
