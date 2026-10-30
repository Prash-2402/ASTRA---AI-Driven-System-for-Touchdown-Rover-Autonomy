from alembic import context
from sqlalchemy import create_engine

from backend.core.config import settings
from backend.database.models import Base

target_metadata = Base.metadata


def run_migrations_online():
    url = context.config.attributes.get("url") or settings.database_url
    connectable = create_engine(url)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()


def run_migrations_offline():
    context.configure(url=settings.database_url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
