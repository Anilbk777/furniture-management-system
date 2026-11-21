"""Alembic async env. Always uses the DIRECT (non-pooled) Neon URL, via asyncpg."""

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.core.database import build_async_url, is_pooled_url
from app.helper.base import Base

# Import every model module so autogenerate can see its tables (one line per module)
import app.modules.auth.auth_models  # noqa: F401
import app.modules.employees.employees_models  # noqa: F401
import app.modules.organization.organization_models  # noqa: F401
import app.modules.party.party_models  # noqa: F401
import app.modules.transaction.transaction_models  # noqa: F401
import app.modules.attendance.attendance_models  # noqa: F401

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# Converts the Neon URL to postgresql+asyncpg (whatever driver the .env URL names)
url, connect_args = build_async_url(settings.direct_database_url)
if is_pooled_url(url):
    raise RuntimeError(
        "DIRECT_DATABASE_URL must be Neon's non-pooled URL (host without '-pooler')."
    )


def run_migrations_offline() -> None:
    context.configure(
        url=url.render_as_string(hide_password=False),
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    engine = create_async_engine(url, poolclass=NullPool, connect_args=connect_args)
    async with engine.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
