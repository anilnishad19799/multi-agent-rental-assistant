"""User repository — extends base with user-specific queries."""
import logging
from typing import Optional, Dict, Any
from sqlalchemy import select
from backend.models.base import get_session
from backend.models import User, UserPreference
from backend.repositories.base_repository import BaseRepository

logger = logging.getLogger(__name__)


class UserRepository(BaseRepository[User]):

    def __init__(self):
        super().__init__(User)

    async def get_by_email(self, email: str) -> Optional[User]:
        async with get_session() as session:
            stmt = select(User).where(User.email == email)
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def get_preferences(self, user_id: str) -> Optional[UserPreference]:
        async with get_session() as session:
            stmt = select(UserPreference).where(UserPreference.user_id == user_id)
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def upsert_user_from_extracted_data(self, data: Dict[str, Any]) -> User:
        """Create or update a user from extracted data dict."""
        email = data.get("email")

        if email:
            existing = await self.get_by_email(email)
            if existing:
                return await self.update(existing.id, **data)

        user = await self.create(**data)
        logger.info(f"Created user from extracted data: {user.id}")
        return user

    async def upsert_preferences(self, user_id: str, prefs: Dict[str, Any]) -> UserPreference:
        """Create or update user preferences."""
        async with get_session() as session:
            stmt = select(UserPreference).where(UserPreference.user_id == user_id)
            result = await session.execute(stmt)
            existing = result.scalar_one_or_none()

            if existing:
                for key, value in prefs.items():
                    if hasattr(existing, key) and value is not None:
                        setattr(existing, key, value)
                await session.commit()
                await session.refresh(existing)
                return existing

            pref = UserPreference(user_id=user_id, **prefs)
            session.add(pref)
            await session.commit()
            await session.refresh(pref)
            return pref
