from logging.config import fileConfig

from alembic import context

import backend.models  # noqa: F401
from backend.core.config import get_settings
from backend.core.database import Base, engine

if context.config.config_file_name is not None:
    fileConfig(context.config.config_file_name)

CONFIGURE_OPTIONS = {"target_metadata": Base.metadata, "compare_server_default": True}


def run_migrations_offline() -> None:
    context.configure(
        url=get_settings().database_url,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        **CONFIGURE_OPTIONS,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    with engine.connect() as connection:
        context.configure(connection=connection, **CONFIGURE_OPTIONS)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
