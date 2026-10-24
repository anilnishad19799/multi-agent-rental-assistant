"""Generic async repository base class using Repository Pattern."""
import logging
from typing import TypeVar, Generic, Type, List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from backend.models.base import Base, get_session

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=Base)


class BaseRepository(Generic[T]):
    """Generic async CRUD repository."""

    def __init__(self, model_class: Type[T]):
        self.model_class = model_class

    async def get_by_id(self, id: str) -> Optional[T]:
        async with get_session() as session:
            result = await session.get(self.model_class, id)
            return result

    async def get_all(self, limit: int = 100) -> List[T]:
        async with get_session() as session:
            stmt = select(self.model_class).limit(limit)
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def create(self, **kwargs) -> T:
        async with get_session() as session:
            obj = self.model_class(**kwargs)
            session.add(obj)
            await session.commit()
            await session.refresh(obj)
            logger.info(f"Created {self.model_class.__name__} with id={obj.id}")
            return obj

    async def update(self, id: str, **kwargs) -> Optional[T]:
        async with get_session() as session:
            obj = await session.get(self.model_class, id)
            if obj is None:
                return None
            for key, value in kwargs.items():
                if hasattr(obj, key) and value is not None:
                    setattr(obj, key, value)
            await session.commit()
            await session.refresh(obj)
            return obj

    async def delete(self, id: str) -> bool:
        async with get_session() as session:
            obj = await session.get(self.model_class, id)
            if obj is None:
                return False
            await session.delete(obj)
            await session.commit()
            return True
