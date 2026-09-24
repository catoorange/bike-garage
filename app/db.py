from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker, Session
from typing import Generator

# Creates bike_garage.db automatically on first run. Swap the URL for Postgres later.
DATABASE_URL = "sqlite:///./bike_garage.db"

class Base(DeclarativeBase):
    pass

engine = create_engine(
    DATABASE_URL,
    echo=False,  # set True to watch generated SQL while learning
    connect_args={"check_same_thread": False},  # required for SQLite + FastAPI threads
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db() -> Generator[Session, None, None]:
    """One DB session per request, closed when the request ends."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()