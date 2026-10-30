import os

import pytest

# Integration tests use a separate database (never the development one).
os.environ.setdefault("ASTRA_DATABASE_URL", "postgresql+psycopg2://astra:astra@localhost:5432/astra_test")
os.environ.setdefault("ASTRA_DATA_DIR", "/tmp/astra_test_data")


@pytest.fixture(scope="session")
def migrated_db():
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import create_engine, text
    url = os.environ["ASTRA_DATABASE_URL"]
    try:
        with create_engine(url).connect() as c:
            c.execute(text("select 1"))
    except Exception as e:  # noqa: BLE001
        pytest.skip(f"PostgreSQL not available: {e}")
    cfg = Config("alembic.ini")
    cfg.attributes["url"] = url
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")
    return url
