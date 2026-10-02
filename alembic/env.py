"""Alembic environment configuration for async SQLAlchemy.

This module configures Alembic to work with our async SQLAlchemy models
and database connection.
"""

import asyncio
from logging.config import fileConfig

from sqlalchemy import MetaData, pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context
from fragrance_rater.core.config import settings
from fragrance_rater.models import Base

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Importing fragrance_rater.models registers every ORM table on Base.metadata
target_metadata = Base.metadata

# Shared by offline and online mode (architecture review D-04).
# compare_type and compare_server_default make autogenerate see column type
# and server-default changes, not just added or dropped columns.
# render_as_batch makes autogenerate emit `op.batch_alter_table` blocks,
# which pass straight through to ALTER TABLE on PostgreSQL and are the only
# form SQLite can execute for constraint or nullability changes.
CONFIGURE_OPTS: dict[str, bool] = {
    "compare_type": True,
    "compare_server_default": True,
    "render_as_batch": True,
}


def _comparison_metadata() -> MetaData | None:
    """Return the model metadata when comparing, ``None`` when executing scripts.

    #CRITICAL: data-integrity: Alembic applies ``target_metadata``'s naming
    convention to every constraint an ``op.*`` call creates without a name
    (``alembic/operations/schemaobj.py``). The migrations before 2c8c3971bfd8
    were written without a convention and rely on PostgreSQL's own names
    (5d2e7c9f9c92 drops ``fragrance_notes_pkey`` by name, and 2c8c3971bfd8
    renames the PostgreSQL names). Passing the model metadata while they run
    would make a fresh database diverge from production and break the chain.
    #VERIFY: upgrade, downgrade, and stamp always carry a destination revision;
    ``revision --autogenerate`` and ``check``, the only commands that compare
    against the models, never do. CI's postgres-integration job upgrades an
    empty database to head and then runs the parity tests, which fail if this
    split is wrong in either direction.

    Returns:
        MetaData | None: ``Base.metadata`` for autogenerate and ``check``;
            ``None`` for upgrade, downgrade, and stamp, which never need it.
    """
    try:
        context.get_revision_argument()
    except KeyError:
        return target_metadata
    return None


def get_url() -> str:
    """Get the database URL from the shared application ``Settings``.

    #ASSUME: data-integrity: this module previously read ``DATABASE_URL``
    from the environment directly, with its own independent hardcoded
    fallback literal duplicating (and able to silently drift from) the one
    in ``fragrance_rater.core.config.Settings.database_url``. Two
    independently-hardcoded defaults for the same setting is itself a bug
    class: whichever one gets edited later becomes the only place that
    reflects reality.
    #VERIFY: this now reads ``settings.database_url`` directly, which is
    itself populated from the ``DATABASE_URL`` env var (or the same single
    placeholder default) via pydantic-settings, so alembic and the app can
    never disagree about which database URL is in effect. Both this
    function and ``run_async_migrations`` below use the async
    (``postgresql+asyncpg://``) form, matching ``async_engine_from_config``.

    Returns:
        str: Database connection URL, sourced from the same ``Settings``
            singleton the application itself uses.
    """
    return settings.database_url


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.
    """
    url = get_url()
    context.configure(
        url=url,
        target_metadata=_comparison_metadata(),
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        **CONFIGURE_OPTS,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Execute migrations with the given connection.

    Args:
        connection (Connection): Database connection to use for migrations.
    """
    context.configure(
        connection=connection,
        target_metadata=_comparison_metadata(),
        **CONFIGURE_OPTS,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations in 'online' mode with async engine.

    In this scenario we need to create an async Engine
    and associate a connection with the context.
    """
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = get_url()

    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
