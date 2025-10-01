import datetime as dt
from datetime import datetime, timezone
datetime.now(timezone.utc)

def login(client, email, password):
    r = client.post("/api/auth/register", json={"email": email, "password": password})
    assert r.status_code in (200, 201)
    r = client.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200

def test_exercises_are_scoped_per_user(client):
    # User A creates two exercises
    login(client, "a@example.com", "p@ssw0rd")
    r = client.post("/api/exercises", json={"name": "Barbell Squat", "category": "strength", "default_unit": "kg", "equipment": None})
    assert r.status_code == 201
    r = client.post("/api/exercises", json={"name": "Bench Press", "category": "strength", "default_unit": "kg", "equipment": None})
    assert r.status_code == 201

    r = client.get("/api/exercises?limit=100")
    assert r.status_code == 200
    a_rows = r.json()
    assert {e["name"] for e in a_rows} == {"Barbell Squat", "Bench Press"}

    # Switch to user B — should see nothing initially
    client.post("/api/auth/logout")
    login(client, "b@example.com", "p@ssw0rd")
    r = client.get("/api/exercises?limit=100")
    assert r.status_code == 200
    b_rows = r.json()
    assert b_rows == []  # scoped correctly

def test_exercise_create_update_delete(client):
    login(client, "x@example.com", "secret123")
    # Create
    r = client.post("/api/exercises", json={"name": "Deadlift", "category": "strength", "default_unit": "kg", "equipment": None})
    assert r.status_code == 201
    ex = r.json()
    ex_id = ex["id"]

    # Update
    r = client.put(f"/api/exercises/{ex_id}", json={"name": "Conventional Deadlift"})
    assert r.status_code == 200
    assert r.json()["name"] == "Conventional Deadlift"

    # Delete
    r = client.delete(f"/api/exercises/{ex_id}")
    assert r.status_code == 204

    # Verify gone
    r = client.get(f"/api/exercises/{ex_id}")
    assert r.status_code == 404

def _login_exercises(client, email="exuser@ex.com", pw="secret123"):
    client.post("/api/auth/register", json={"email": email, "password": pw})
    r = client.post("/api/auth/login", json={"email": email, "password": pw})
    assert r.status_code == 200

def test_exercises_chronological_by_id_desc(client):
    _login_exercises(client)
    # Create in arbitrary names (so ABC order would differ)
    for n in ["Zed Move", "Alpha Press", "Beta Row"]:
        r = client.post("/api/exercises", json={"name": n, "category": "strength"})
        assert r.status_code in (200, 201)

    r = client.get("/api/exercises?limit=100")
    assert r.status_code == 200
    rows = r.json()
    ids = [row["id"] for row in rows]
    assert ids == sorted(ids, reverse=True)

def test_exercises_name_and_category_filters(client):
    _login_exercises(client)
    client.post("/api/exercises", json={"name": "Leg Press", "category": "strength"})
    client.post("/api/exercises", json={"name": "Jogging", "category": "cardio"})
    client.post("/api/exercises", json={"name": "Shoulder Press", "category": "strength"})

    r = client.get("/api/exercises?q=press&limit=50")
    assert r.status_code == 200
    names = [e["name"].lower() for e in r.json()]
    assert "leg press" in names and "shoulder press" in names
    assert "jogging" not in names

    r = client.get("/api/exercises?category=cardio&limit=50")
    assert r.status_code == 200
    cats = [e["category"] for e in r.json()]
    assert all(c == "cardio" for c in cats)

def test_delete_exercise_in_use_returns_409_and_usage(client):
    _login_exercises(client)

    # exercise
    ex = client.post("/api/exercises", json={"name": "Row Machine", "category": "strength"}).json()
    # workout template
    tpl = client.post("/api/workouts", json={"name": "Back Day"}).json()
    # add item using the exercise
    ir = client.post(f"/api/workouts/{tpl['id']}/items", json={
        "exercise_id": ex["id"], "planned_sets": 3, "planned_reps": 10
    })
    assert ir.status_code in (200, 201)

    # deletion should be blocked
    dr = client.delete(f"/api/exercises/{ex['id']}")
    assert dr.status_code == 409

    # usage endpoint shows references
    ur = client.get(f"/api/exercises/{ex['id']}/usage")
    assert ur.status_code == 200
    usage = ur.json()
    assert usage["counts"]["workouts"] >= 1

def _login(client, email="alice2@example.com"):
    client.post("/api/auth/register", json={"email": email, "password": "secret123"})
    r = client.post("/api/auth/login", json={"email": email, "password": "secret123"})
    assert r.status_code == 200


def test_exercise_validation_and_duplicates(client):
    _login(client, "val@example.com")

    # empty name -> 400
    r = client.post("/api/exercises", json={"name": "   ", "category": "strength"})
    assert r.status_code == 400

    # create
    r = client.post("/api/exercises", json={"name": "Bench Press", "category": "strength"})
    assert r.status_code in (200, 201)

    # duplicate (case-insensitive) -> 409
    r = client.post("/api/exercises", json={"name": "bench press", "category": "strength"})
    assert r.status_code == 409


def test_exercises_per_user_isolation(client):
    # Alice creates an exercise
    _login(client, "alice_iso@example.com")
    r = client.post("/api/exercises", json={"name": "Alice Only Move", "category": "strength"})
    assert r.status_code in (200, 201)
    client.post("/api/auth/logout")

    # Bob logs in and should not see Alice's exercise
    _login(client, "bob_iso@example.com")
    r = client.get("/api/exercises?limit=200")
    assert r.status_code == 200
    names = [row["name"] for row in r.json()]
    assert "Alice Only Move" not in names  # isolation


def test_exercise_search_is_case_insensitive(client):
    _login(client, "search@example.com")
    client.post("/api/exercises", json={"name": "Shoulder Press", "category": "strength"})
    client.post("/api/exercises", json={"name": "bench PRESS", "category": "strength"})

    r = client.get("/api/exercises?q=press&limit=100")
    assert r.status_code == 200
    names = [e["name"].lower() for e in r.json()]
    # both should be found regardless of case
    assert "shoulder press" in names
    assert "bench press" in names


def test_delete_exercise_referenced_by_session_returns_409(client):
    # login
    _login(client, "del409@example.com")
    # make exercise
    r = client.post("/api/exercises", json={"name": "Row 409", "category": "strength"})
    ex_id = r.json()["id"]

    # create a workout template and use the exercise (so we can create session from it)
    wr = client.post("/api/workouts", json={"name": "T409"})
    assert wr.status_code in (200, 201)
    tpl_id = wr.json()["id"]
    client.post(f"/api/workouts/{tpl_id}/items", json={"exercise_id": ex_id, "planned_sets": 3, "planned_reps": 10})

    # create session from template (so the exercise is referenced by a session item)
    today = dt.date.today().isoformat()
    sr = client.post("/api/sessions", json={"date": today, "title": "S409", "workout_template_id": tpl_id})
    assert sr.status_code in (200, 201)

    # now delete exercise -> 409
    dr = client.delete(f"/api/exercises/{ex_id}")
    assert dr.status_code == 409

    # usage endpoint should mention a session
    ur = client.get(f"/api/exercises/{ex_id}/usage")
    assert ur.status_code == 200
    body = ur.json()
    assert body["counts"]["sessions"] >= 1