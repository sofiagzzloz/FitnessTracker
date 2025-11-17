from sqlmodel import SQLModel, create_engine, Session
from sqlalchemy import event
from sqlalchemy.engine import Engine
import os
import sys
import traceback

DEFAULT_DB_URL = "postgresql+psycopg://fitness:fitness@localhost:5432/fitness"
if "DATABASE_URL" not in os.environ:
    raise RuntimeError("❌ DATABASE_URL is missing! Make sure it is set in Azure Container App.")

DATABASE_URL = os.environ["DATABASE_URL"]


print(f"🚀 Using DATABASE_URL = {DATABASE_URL}", flush=True)

connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(
    DATABASE_URL,
    echo=True,  # 👈 SHOW SQL logs
    connect_args=connect_args
)

# SQLite foreign keys if needed
if DATABASE_URL.startswith("sqlite"):
    @event.listens_for(Engine, "connect")
    def set_sqlite_pragma(dbapi_conn, _):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON;")
        cursor.close()


def init_db() -> None:
    print("⚙️  Running init_db()...", flush=True)
    try:
        from . import models
        SQLModel.metadata.create_all(engine)
        print("✅ init_db completed successfully!", flush=True)
    except Exception as e:
        print("❌ init_db FAILED:", e, flush=True)
        traceback.print_exc()
        sys.exit(1)  # ❗ force crash so Azure shows logs


def get_session():
    with Session(engine) as session:
        yield session