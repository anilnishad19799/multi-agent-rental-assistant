import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./rental_system.db")

connect_args = {"timeout": 30} if "sqlite" in DATABASE_URL else {}
engine = create_async_engine(DATABASE_URL, echo=False, connect_args=connect_args)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

Base = declarative_base()

@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session

async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        
        def migrate_schema(sync_conn):
            from sqlalchemy import text
            try:
                # Enable WAL mode and busy timeout for concurrent access
                sync_conn.execute(text("PRAGMA journal_mode=WAL;"))
                sync_conn.execute(text("PRAGMA busy_timeout=30000;"))
                cols = [r[1] for r in sync_conn.execute(text("PRAGMA table_info(users)")).fetchall()]
                if cols and "password_hash" not in cols:
                    sync_conn.execute(text("ALTER TABLE users ADD COLUMN password_hash VARCHAR"))
                if cols and "is_admin" not in cols:
                    sync_conn.execute(text("ALTER TABLE users ADD COLUMN is_admin BOOLEAN DEFAULT 0"))
            except Exception:
                pass
        
        await conn.run_sync(migrate_schema)
