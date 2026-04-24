"""SQLAlchemy async database setup."""
import ssl
from collections.abc import AsyncGenerator
from typing import Any
from urllib.parse import parse_qs, urlencode, urlsplit, urlunsplit

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings

settings = get_settings()


def _prepare_db_url(url: str) -> tuple[str, dict]:
    """Prepare a DATABASE_URL for asyncpg.

    1. Convert postgres:// or postgresql:// → postgresql+asyncpg://
    2. Strip ``sslmode`` query param (asyncpg doesn't support it as a
       libpq-style DSN parameter).  If sslmode was present and not
       'disable', pass an SSLContext via ``connect_args`` instead.

    Returns (cleaned_url, connect_args_dict).
    """
    # ── scheme fix ──
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+asyncpg://", 1)
    elif url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)

    # ── strip sslmode ──
    parts = urlsplit(url)
    qs = parse_qs(parts.query)
    sslmode = qs.pop("sslmode", [None])
    new_query = urlencode(qs, doseq=True)
    url = urlunsplit((parts.scheme, parts.netloc, parts.path, new_query, parts.fragment))

    connect_args: dict = {}
    if sslmode and sslmode[0] not in ("disable", None):
        # DigitalOcean managed PG requires SSL but uses self-signed certs
        ssl_ctx = ssl.create_default_context()
        ssl_ctx.check_hostname = False
        ssl_ctx.verify_mode = ssl.CERT_NONE
        connect_args["ssl"] = ssl_ctx

    return url, connect_args


_database_configuration_error = settings.database_configuration_error

engine = None
async_session_factory = None

if _database_configuration_error is None:
    _db_url, _connect_args = _prepare_db_url(settings.resolved_database_url)

    engine = create_async_engine(
        _db_url,
        echo=settings.DEBUG,
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20,
        connect_args=_connect_args,
    )

    async_session_factory = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
else:
    _db_url = None
    _connect_args: dict[str, Any] = {}


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""
    pass


# Alias for direct use outside FastAPI (seed scripts, background tasks)
AsyncSessionLocal = async_session_factory


def get_database_configuration_error() -> str | None:
    """Return a human-readable configuration error for the database, if any."""
    return _database_configuration_error


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency — yields a DB session per request."""
    if async_session_factory is None:
        raise RuntimeError(
            get_database_configuration_error()
            or "Database session factory is unavailable"
        )
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
