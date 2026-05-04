"""
openclaw/backend/db/session.py
Async SQLAlchemy engine + session factory.
Call init_db() once on startup to create all tables.
"""
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.config import get_settings
from backend.db.models import Base
# Ensure all mapped classes are registered with Base.metadata before create_all
from backend.search.complexity_models import ComplexityResult, ComplexitySection, ComplexityFactor  # noqa: F401

settings = get_settings()

# Single engine instance for the process lifetime
engine = create_async_engine(
    settings.database_url,
    echo=settings.is_dev,   # SQL logging in dev only
    future=True,
    # SQLite-specific: allow concurrent reads
    connect_args={"check_same_thread": False} if "sqlite" in settings.database_url else {},
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


async def init_db() -> None:
    """Create all tables. Called once at app startup."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Async context manager for a DB session.
    Use in engine workers and internal services:
        async with get_session() as session:
            ...
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency — yields a session per request.
    Usage:
        async def route(db: AsyncSession = Depends(get_db)):
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
