from typing import AsyncGenerator
import logging
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool
from sqlalchemy import text
from app.core.config import settings


logger = logging.getLogger("inference-core-v2.database")


# Create async engine
engine = create_async_engine(
    settings.database_url.replace("postgresql://", "postgresql+asyncpg://"),
    echo=False,
    poolclass=NullPool,  # Use NullPool for better async performance
    future=True
)

# Create async session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False
)


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency to get database session"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_database():
    """Initialize database connection - tables are managed via migrations"""
    # Tables are created via SQL migrations, not ORM
    # Just verify connection is working
    async with engine.begin() as conn:
        await conn.execute(text("SELECT 1"))
    logger.info("Database connection verified")


async def close_database():
    """Close database connections"""
    await engine.dispose()