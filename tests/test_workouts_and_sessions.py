import datetime as dt

def login(client, email, password):
    client.post("/api/auth/register", json={"email": email, "password": password})
    client.post("/api/auth/login", json={"email": email, "password": password})

def test_workout_template_and_make_session(client):
    login(client, "c@example.com", "secret123")

    # Seed exercises
    squat = client.post("/api/exercises", json={"name": "Squat", "category": "strength", "default_unit": "kg", "equipment": None}).json()
    row   = client.post("/api/exercises", json={"name": "Row", "category": "strength", "default_unit": "kg", "equipment": None}).json()

    # Create template
    r = client.post("/api/workouts", json={"name": "Lower A"})
    assert r.status_code == 201
    tpl = r.json()

    # Add items (order should be maintained)
    r = client.post(f"/api/workouts/{tpl['id']}/items", json={"exercise_id": squat["id"], "planned_sets": 3, "planned_reps": 5})
    assert r.status_code == 201
    r = client.post(f"/api/workouts/{tpl['id']}/items", json={"exercise_id": row["id"], "planned_sets": 3, "planned_reps": 8})
    assert r.status_code == 201

    # List items
    r = client.get(f"/api/workouts/{tpl['id']}/items")
    assert r.status_code == 200
    items = r.json()
    assert [it["exercise_id"] for it in items] == [squat["id"], row["id"]]

    # Make a session from the template
    today = dt.date.today().isoformat()
    r = client.post(f"/api/workouts/{tpl['id']}/make-session", params={"session_date": today})
    assert r.status_code == 201
    sess = r.json()

    # Session should have the items (via list)
    r = client.get(f"/api/sessions/{sess['id']}/items")
    assert r.status_code == 200
    sitems = r.json()
    assert len(sitems) == 2
    assert [si["exercise_id"] for si in sitems] == [squat["id"], row["id"]]

    # Delete the session
    r = client.delete(f"/api/sessions/{sess['id']}")
    assert r.status_code == 204