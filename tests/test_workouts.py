from fastapi.testclient import TestClient
from sqlmodel import SQLModel, create_engine, Session

from app.main import app
from app.db import get_session

def test_create_then_get_workout(tmp_path):
    test_db_url = f"sqlite:///{tmp_path/'test.db'}"
    engine = create_engine(test_db_url, connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)

    def override_session():
        with Session(engine) as s:
            yield s

    app.dependency_overrides[get_session] = override_session
    client = TestClient(app)

    # create
    payload = {"date": "2025-09-17", "exercise": "Squat", "sets": 4, "reps": 8, "weight_kg": 60}
    r = client.post("/workouts", json=payload)
    assert r.status_code == 201
    wid = r.json()["id"]

    # read back
    r2 = client.get(f"/workouts/{wid}")
    assert r2.status_code == 200
    assert r2.json()["exercise"] == "Squat"
