import os
import sys
import tempfile
import contextlib

# --- ensure project root is importable ---
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import pytest
from fastapi.testclient import TestClient
from sqlmodel import SQLModel, create_engine, Session

from app.main import app
from app.db import get_session as prod_get_session

@pytest.fixture(scope="session")
def _test_db_url():
    fd, path = tempfile.mkstemp(prefix="ft_test_", suffix=".db")
    os.close(fd)
    try:
        yield f"sqlite:///{path}"
    finally:
        with contextlib.suppress(FileNotFoundError):
            os.remove(path)

@pytest.fixture(scope="session")
def _engine(_test_db_url):
    engine = create_engine(_test_db_url, connect_args={"check_same_thread": False})
    # Import models to register metadata, then create tables
    from app import models  # noqa: F401
    SQLModel.metadata.create_all(engine)
    return engine

@pytest.fixture
def db(_engine):
    with Session(_engine) as s:
        yield s

@pytest.fixture
def client(db, _engine):
    # Override the app's DB session dependency to use the test engine
    def _get_session_override():
        with Session(_engine) as s:
            yield s

    app.dependency_overrides[prod_get_session] = _get_session_override
    try:
        with TestClient(app) as c:
            yield c
    finally:
        app.dependency_overrides.clear()