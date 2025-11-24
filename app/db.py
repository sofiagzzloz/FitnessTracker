import os
import sys
import traceback

from dotenv import load_dotenv
from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlmodel import SQLModel, Session, create_engine

load_dotenv()

DEFAULT_DB_URL = "sqlite:///./fitness.db"
ENVIRONMENT = os.getenv("ENV", "development").lower()

if os.getenv("DATABASE_URL"):
    DATABASE_URL = os.environ["DATABASE_URL"]
else:
    if ENVIRONMENT == "production":
        raise RuntimeError(
            "DATABASE_URL is required in production. Set it to your Azure PostgreSQL connection string."
        )
    DATABASE_URL = DEFAULT_DB_URL

print(f"🚀 Using DATABASE_URL = {DATABASE_URL}", flush=True)

connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(
    DATABASE_URL,
    echo=os.getenv("SQL_ECHO", "false").lower() == "true",
    connect_args=connect_args,
)

# SQLite foreign keys if needed
if DATABASE_URL.startswith("sqlite"):
    @event.listens_for(Engine, "connect")
    def set_sqlite_pragma(dbapi_conn, _):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON;")
        cursor.close()


def init_db() -> None:
    print("  Running init_db()...", flush=True)
    try:
        from . import models
        SQLModel.metadata.create_all(engine)
        print(" init_db completed successfully!", flush=True)
    except Exception as e:
        print(" init_db FAILED:", e, flush=True)
        traceback.print_exc()
        sys.exit(1)  #  force crash so Azure shows logs


def get_session():
    with Session(engine) as session:
        yield session
        