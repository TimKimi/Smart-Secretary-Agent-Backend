from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.ssa.config import settings
from src.ssa.db.base import Base

engine = create_async_engine(settings.database_url, echo=settings.debug)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
