from __future__ import annotations

from contextlib import contextmanager

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from backend.core.config import settings

_engine = None
_Session = None


def init_engine(url: str | None = None):
    global _engine, _Session
    target_url = url or settings.database_url
    connect_args = {}
    if "sqlite" in target_url:
        connect_args["check_same_thread"] = False
    _engine = create_engine(target_url, pool_pre_ping=True, future=True, connect_args=connect_args)
    _Session = sessionmaker(bind=_engine, expire_on_commit=False)
    return _engine


def engine():
    if _engine is None:
        init_engine()
    return _engine


@contextmanager
def session_scope():
    if _Session is None:
        init_engine()
    s = _Session()
    try:
        yield s
        s.commit()
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()


def db_status() -> dict:
    try:
        with engine().connect() as c:
            try:
                v = c.execute(text("select version()")).scalar()
            except Exception:
                v = f"SQLite {c.execute(text('select sqlite_version()')).scalar()}"
            try:
                rev = c.execute(text("select version_num from alembic_version")).scalar()
            except Exception:  # noqa: BLE001
                rev = None
        return {"connected": True, "server": str(v).split(" on ")[0], "migration": rev}
    except Exception as e:  # noqa: BLE001
        return {"connected": False, "error": str(e).splitlines()[0]}
