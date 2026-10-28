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
        if not email:
            return None
        clean_email = email.strip().lower()
        async with get_session() as session:
            stmt = select(User).where(User.email == clean_email)
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def create_user_with_password(
        self,
        email: str,
        password_hash: str,
        name: str,
        phone: Optional[str] = None,
        is_admin: bool = False,
    ) -> User:
        """Create a new registered user with hashed password."""
        return await self.create(
            email=email.strip().lower(),
            password_hash=password_hash,
            name=name.strip(),
            phone=phone.strip() if phone else None,
            is_admin=is_admin,
        )

    async def ensure_admin_user(
        self,
        email: str = "admin@gmail.com",
        password: str = "Admin@1234",
    ) -> User:
        """Ensure the administrator account exists with designated password and privileges."""
        clean_email = email.strip().lower()
        from backend.services.auth_service import hash_password, verify_password

        existing = await self.get_by_email(clean_email)
        if existing:
            needs_update = False
            if not existing.is_admin:
                needs_update = True
            if not verify_password(password, existing.password_hash):
                needs_update = True

            if needs_update:
                new_pw_hash = hash_password(password)
                async with get_session() as session:
                    stmt = select(User).where(User.id == existing.id)
                    res = await session.execute(stmt)
                    u = res.scalar_one_or_none()
                    if u:
                        u.is_admin = True
                        u.password_hash = new_pw_hash
                        if not u.name or u.name == "Admin":
                            u.name = "System Admin"
                        await session.commit()
                        logger.info(f"Updated administrator account credentials: {clean_email}")
            return existing

        pw_hash = hash_password(password)
        admin_user = await self.create_user_with_password(
            email=clean_email,
            password_hash=pw_hash,
            name="System Admin",
            is_admin=True,
        )
        logger.info(f"Initialized default administrator account: {clean_email}")
        return admin_user

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
