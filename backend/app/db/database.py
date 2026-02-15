from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import NullPool
from app.config import get_settings


def _build_async_url(url: str) -> str:
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+asyncpg://", 1)
    return url


_engine = None
_session_factory = None


def get_engine():
    global _engine
    if _engine is None:
        settings = get_settings()
        _async_url = _build_async_url(settings.DATABASE_URL)
        _engine = create_async_engine(
            _async_url,
            echo=False,
            poolclass=NullPool,
            connect_args={"ssl": False},
        )
    return _engine


def get_session_factory():
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(get_engine(), class_=AsyncSession, expire_on_commit=False)
    return _session_factory


engine = property(lambda self: get_engine())


async def get_db() -> AsyncSession:
    factory = get_session_factory()
    async with factory() as session:
        yield session
