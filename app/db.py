from sqlmodel import SQLModel, create_engine, Session
from sqlalchemy import event
from sqlalchemy.engine import Engine
import os

# Always use fitness.db unless DATABASE_URL override is set
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///fitness.db")
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, echo=False, connect_args=connect_args)

# Enforce foreign keys for SQLite
@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_conn, _):
    try:
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON;")
        cursor.close()
    except Exception:
        pass

def init_db() -> None:
    from . import models
    SQLModel.metadata.create_all(engine)

def get_session():
    with Session(engine) as session:
        yield session