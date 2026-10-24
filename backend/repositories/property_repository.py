"""Property repository — search and detail queries."""
import logging
from typing import List, Optional
from sqlalchemy import select, and_, or_
from sqlalchemy.orm import selectinload
from backend.models.base import get_session
from backend.models import Property, PropertyConfig
from backend.repositories.base_repository import BaseRepository

logger = logging.getLogger(__name__)


class PropertyRepository(BaseRepository[Property]):

    def __init__(self):
        super().__init__(Property)

    async def search_properties(
        self,
        city: Optional[str] = None,
        area: Optional[str] = None,
        budget_max: Optional[float] = None,
        beds: Optional[int] = None,
        sharing_types: Optional[str] = None,
        property_type: Optional[str] = None,
        food_included: Optional[bool] = None,
        limit: int = 20,
    ) -> List[Property]:
        """Search properties with filters. Returns properties with their configs loaded.

        Handles the common case where user provides an area name (e.g. "Hadapsar")
        without specifying the city. The search checks BOTH city and area columns
        so "Hadapsar" will match area="Hadapsar" even if city="Pune".
        """
        async with get_session() as session:
            stmt = (
                select(Property)
                .options(
                    selectinload(Property.configs),
                    selectinload(Property.amenities),
                    selectinload(Property.images),
                    selectinload(Property.landlord_preferences),
                )
                .where(Property.is_active == True)
            )

            # Location filter: search BOTH city and area columns with OR logic
            # so "Hadapsar" matches even if it's stored as area not city
            location_filters = []
            if city:
                location_filters.append(Property.city.ilike(f"%{city}%"))
                # Also try city value against area column
                location_filters.append(Property.area.ilike(f"%{city}%"))
            if area:
                location_filters.append(Property.area.ilike(f"%{area}%"))
                # Also try area value against city column
                location_filters.append(Property.city.ilike(f"%{area}%"))

            if location_filters:
                stmt = stmt.where(or_(*location_filters))

            if property_type:
                stmt = stmt.where(Property.property_type.ilike(property_type))

            result = await session.execute(stmt)
            properties = list(result.scalars().unique().all())

            # Post-filter by config criteria (budget, beds, sharing, food)
            filtered = []
            for prop in properties:
                matching_configs = []
                for config in prop.configs:
                    match = True
                    if budget_max and config.rent and config.rent > budget_max:
                        match = False
                    if beds and config.available_beds is not None and config.available_beds < beds:
                        match = False
                    if sharing_types:
                        requested = [int(s.strip()) for s in str(sharing_types).split(",") if s.strip().isdigit()]
                        if requested and config.sharing_type and config.sharing_type not in requested:
                            match = False
                    if food_included is not None and config.food_included != food_included:
                        match = False
                    if match:
                        matching_configs.append(config)

                if matching_configs:
                    filtered.append(prop)

            logger.info(
                f"Property search: city={city}, area={area}, budget={budget_max}, "
                f"sharing={sharing_types}, type={property_type} → "
                f"{len(filtered)}/{len(properties)} matched"
            )
            return filtered[:limit]

    async def search_with_user_criteria(
        self,
        city: Optional[str] = None,
        area: Optional[str] = None,
        budget_max: Optional[float] = None,
        beds: Optional[int] = None,
        sharing_types: Optional[str] = None,
        property_type: Optional[str] = None,
        food_included: Optional[bool] = None,
        user_gender: Optional[str] = None,
        user_age: Optional[int] = None,
        user_profession: Optional[str] = None,
        cooking_needed: Optional[bool] = None,
        limit: int = 20,
    ) -> List[Property]:
        """Search properties AND filter by landlord preferences against user profile.

        This is called after both rent criteria and user info are collected,
        matching landlord preferences (gender, age, profession, cooking) against
        the user's profile for better results.
        """
        # First get properties matching search criteria
        properties = await self.search_properties(
            city=city, area=area, budget_max=budget_max,
            beds=beds, sharing_types=sharing_types,
            property_type=property_type, food_included=food_included,
            limit=100,  # Get more, then filter by user criteria
        )

        if not properties:
            return []

        # Filter by landlord preferences vs user profile
        matched = []
        for prop in properties:
            landlord_ok = True
            for lp in prop.landlord_preferences:
                # Gender check
                if lp.gender and lp.gender != "ANY" and user_gender:
                    if user_gender.upper() != lp.gender.upper():
                        landlord_ok = False

                # Age check
                if user_age:
                    if lp.min_age and user_age < lp.min_age:
                        landlord_ok = False
                    if lp.max_age and user_age > lp.max_age:
                        landlord_ok = False

                # Profession check
                if lp.profession and user_profession:
                    if user_profession.upper() != lp.profession.upper():
                        landlord_ok = False

                # Cooking check
                if lp.no_cooking and cooking_needed:
                    landlord_ok = False

            # If no landlord preferences set, property is open to all
            if not prop.landlord_preferences:
                landlord_ok = True

            if landlord_ok:
                matched.append(prop)

        logger.info(
            f"User-filtered search: {len(matched)}/{len(properties)} matched "
            f"(gender={user_gender}, age={user_age}, cooking={cooking_needed})"
        )
        return matched[:limit]

    async def get_property_with_details(self, property_id: str) -> Optional[Property]:
        """Get a single property with all related data loaded."""
        async with get_session() as session:
            stmt = (
                select(Property)
                .options(
                    selectinload(Property.configs),
                    selectinload(Property.amenities),
                    selectinload(Property.images),
                    selectinload(Property.landlord_preferences),
                )
                .where(Property.id == property_id)
            )
            result = await session.execute(stmt)
            return result.scalar_one_or_none()
