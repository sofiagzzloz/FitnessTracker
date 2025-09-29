# tests/test_exercises.py
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