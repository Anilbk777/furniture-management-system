"""Async database connection for Neon PostgreSQL.  Put this at app/db/database.py.

Two URLs, two jobs (both set in .env, read by app/core/config.py):
  * DATABASE_URL         -> POOLED Neon URL (host contains "-pooler"). Used here, by the app.
  * DIRECT_DATABASE_URL  -> NON-POOLED Neon URL. Used only by Alembic (alembic/env.py).
"""

import asyncio
import ssl
from collections.abc import AsyncIterator

from sqlalchemy import text
from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)

LOCAL_HOSTS = {"", "localhost", "127.0.0.1", "::1"}  # "" = unix socket


def is_pooled_url(url: URL) -> bool:
    """Neon pooled hosts contain '-pooler'."""
    return "-pooler" in (url.host or "")


def build_async_url(raw_url: str) -> tuple[URL, dict]:
    """Convert a Neon URL into an asyncpg URL + connect_args.

    asyncpg rejects `sslmode` / `channel_binding`, so we strip them and set up TLS
    ourselves: remote hosts always get verified TLS, localhost gets none.
    """
    url = make_url(raw_url).set(drivername="postgresql+asyncpg")

    params = dict(url.query)
    sslmode = params.pop("sslmode", None)
    params.pop("ssl", None)
    params.pop("channel_binding", None)
    url = url.set(query=params)

    if url.host in LOCAL_HOSTS:
        return url, {}
    if sslmode == "disable":
        raise ValueError(f"Refusing to connect to remote host {url.host} without TLS")
    return url, {"ssl": ssl.create_default_context()}  # verifies cert + hostname


url, ssl_args = build_async_url(settings.database_url)

engine = create_async_engine(
    url,
    echo=settings.debug,
    pool_size=5,  # small is enough: Neon's pooler multiplexes for us
    max_overflow=5,  # extra connections allowed during bursts
    pool_timeout=30,  # seconds to wait for a free connection
    pool_recycle=300,  # replace connections older than 5 min (Neon closes idle ones)
    pool_pre_ping=True,  # test a connection before use; reconnect if it was dropped
    connect_args={
        **ssl_args,
        "timeout": 15,  # seconds to connect (Neon may be waking up)
        "command_timeout": 30,  # seconds per query
        # PgBouncer (transaction mode) can break asyncpg's prepared statement cache
        "statement_cache_size": 0,
        "prepared_statement_cache_size": 0,
    },
)

AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)


async def get_db() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency: one session per request, closed (and rolled back on error)."""
    async with AsyncSessionLocal() as session:
        yield session


async def ping_db() -> None:
    """Raises if the database can't run a trivial query."""
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))


async def wait_for_db(retries: int = 5, delay: float = 2) -> None:
    """Startup check; retries because Neon can take a few seconds to wake up."""
    for attempt in range(1, retries + 1):
        try:
            await ping_db()
            logger.info("Database connection OK")
            return
        except (SQLAlchemyError, OSError, TimeoutError) as exc:
            logger.warning(f"DB not ready (attempt {attempt}/{retries}): {exc!r}")
            if attempt == retries:
                raise
            await asyncio.sleep(delay)


async def dispose_engine() -> None:
    """Close all pooled connections (call on app shutdown)."""
    await engine.dispose()