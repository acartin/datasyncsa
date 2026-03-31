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
        # Backward-compatible safety net for scoring worker rollout.
        # Production should still apply SQL migrations from /migrations.
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS lead_scoring_jobs (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                lead_id UUID NOT NULL REFERENCES lead_leads(id) ON DELETE CASCADE,
                conversation_id UUID NOT NULL,
                client_id UUID NOT NULL,
                model_id UUID NULL,
                prompt_id UUID NULL,
                generation BIGINT NOT NULL DEFAULT 1,
                running_generation BIGINT NULL,
                expected_lead_messages INTEGER NULL,
                status VARCHAR(24) NOT NULL DEFAULT 'queued',
                attempts INTEGER NOT NULL DEFAULT 0,
                max_attempts INTEGER NOT NULL DEFAULT 3,
                scheduled_for TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                started_at TIMESTAMPTZ NULL,
                finished_at TIMESTAMPTZ NULL,
                last_error_code VARCHAR(64) NULL,
                last_error_message TEXT NULL,
                fallback_used BOOLEAN NOT NULL DEFAULT FALSE,
                json_valid BOOLEAN NULL,
                latency_ms INTEGER NULL,
                response_chars INTEGER NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                CONSTRAINT chk_lead_scoring_jobs_status
                    CHECK (status IN ('queued', 'running', 'rescheduled', 'completed', 'degraded', 'failed', 'cancelled'))
            )
        """))
        await conn.execute(text("""
            CREATE UNIQUE INDEX IF NOT EXISTS uq_lead_scoring_jobs_conversation
            ON lead_scoring_jobs(conversation_id)
        """))
        await conn.execute(text("""
            ALTER TABLE lead_scoring_jobs
            ADD COLUMN IF NOT EXISTS generation BIGINT NOT NULL DEFAULT 1
        """))
        await conn.execute(text("""
            ALTER TABLE lead_scoring_jobs
            ADD COLUMN IF NOT EXISTS running_generation BIGINT NULL
        """))
        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_lead_scoring_jobs_status_scheduled
            ON lead_scoring_jobs(status, scheduled_for)
        """))
        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_lead_scoring_jobs_lead_created
            ON lead_scoring_jobs(lead_id, created_at DESC)
        """))
    logger.info("Database connection verified")


async def close_database():
    """Close database connections"""
    await engine.dispose()
