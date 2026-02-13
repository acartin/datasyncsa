from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from sqlalchemy import text
from app.config.settings import settings

class Base(DeclarativeBase):
    pass

# Initialize Async Engine
# echo=True prints SQL statements to console (useful for debugging "Zero ORM" compliance)
engine = create_async_engine(
    settings.database_url,
    echo=False,
    future=True
)

async_session_maker = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def get_async_session():
    """
    Dependency for SQLAlchemy ORM sessions (Required for FastAPI Users)
    """
    async with async_session_maker() as session:
        yield session

async def get_db_connection():
    """
    Dependency to yield an async database connection (Raw SQL).
    """
    async with engine.connect() as conn:
        yield conn
