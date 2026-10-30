import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.database.models import Base

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./database/astra.db")

# For SQLite, ensure connect_args allows multi-threading
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    pool_pre_ping=True
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    # Ensure database directory exists for SQLite
    if DATABASE_URL.startswith("sqlite"):
        db_path = DATABASE_URL.replace("sqlite:///", "")
        os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
    Base.metadata.create_all(bind=engine)

# Auto-initialize database schema
init_db()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
