import datetime as dt
from datetime import datetime, timezone
datetime.now(timezone.utc)

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

def _login_ws(client, email="ws@ex.com", pw="pw123456"):
    client.post("/api/auth/register", json={"email": email, "password": pw})
    client.post("/api/auth/login", json={"email": email, "password": pw})

def _make_ex(client, name, cat="strength"):
    r = client.post("/api/exercises", json={"name": name, "category": cat})
    assert r.status_code in (200, 201)
    return r.json()["id"]

def test_workout_items_order_and_muscles_summary(client):
    _login_ws(client)

    ex1 = _make_ex(client, "Bench Press")
    ex2 = _make_ex(client, "Lat Pulldown")

    tpl = client.post("/api/workouts", json={"name": "Upper A"}).json()

    # add items in order
    client.post(f"/api/workouts/{tpl['id']}/items", json={"exercise_id": ex1, "planned_sets": 3, "planned_reps": 8})
    client.post(f"/api/workouts/{tpl['id']}/items", json={"exercise_id": ex2, "planned_sets": 4, "planned_reps": 10})

    li = client.get(f"/api/workouts/{tpl['id']}/items").json()
    assert [i["exercise_id"] for i in li] == [ex1, ex2]

    ms = client.get(f"/api/workouts/{tpl['id']}/muscles")
    assert ms.status_code == 200
    summary = ms.json()
    assert "primary" in summary and "secondary" in summary

def test_session_from_template_flow(client):
    _login_ws(client)

    e1 = _make_ex(client, "Squat")
    e2 = _make_ex(client, "Romanian Deadlift")

    tpl = client.post("/api/workouts", json={"name": "Lower A"}).json()
    client.post(f"/api/workouts/{tpl['id']}/items", json={"exercise_id": e1, "planned_sets": 5, "planned_reps": 5})
    client.post(f"/api/workouts/{tpl['id']}/items", json={"exercise_id": e2, "planned_sets": 3, "planned_reps": 8})

    # create session from template
    s = client.post("/api/sessions", json={
        "date": "2024-01-02", "title": "Legs", "workout_template_id": tpl["id"]
    }).json()

    items = client.get(f"/api/sessions/{s['id']}/items").json()
    assert [it["exercise_id"] for it in items] == [e1, e2]

    # patch a note ("actuals")
    first = items[0]
    pr = client.patch(f"/api/sessions/{s['id']}/items/{first['id']}", json={"notes": "3x5 @ 100kg"})
    assert pr.status_code == 200
    assert pr.json()["notes"] == "3x5 @ 100kg"

    # delete an item then delete the session
    di = client.delete(f"/api/sessions/{s['id']}/items/{first['id']}")
    assert di.status_code in (200, 204)

    ds = client.delete(f"/api/sessions/{s['id']}")
    assert ds.status_code in (200, 204)


def _login(client, email):
    client.post("/api/auth/register", json={"email": email, "password": "secret123"})
    r = client.post("/api/auth/login", json={"email": email, "password": "secret123"})
    assert r.status_code == 200


def test_workouts_and_sessions_are_user_scoped(client):
    # Alice creates a workout and a session
    _login(client, "alice_scope@example.com")
    client.post("/api/exercises", json={"name": "Scoped Press", "category": "strength"})
    wr = client.post("/api/workouts", json={"name": "Alice W"})
    assert wr.status_code in (200, 201)
    wid = wr.json()["id"]

    # session from template
    today = dt.date.today().isoformat()
    sr = client.post("/api/sessions", json={"date": today, "title": "Alice S", "workout_template_id": wid})
    assert sr.status_code in (200, 201)
    client.post("/api/auth/logout")

    # Bob should see no Alice data
    _login(client, "bob_scope@example.com")
    # workouts list
    r = client.get("/api/workouts")
    assert r.status_code == 200
    assert all(w["name"] != "Alice W" for w in r.json())
    # sessions list
    r = client.get("/api/sessions")
    assert r.status_code == 200
    assert all(s["title"] != "Alice S" for s in r.json())


def test_session_cannot_be_future_dated(client):
    _login(client, "futured@example.com")
    # tomorrow
    tomorrow = (dt.date.today() + dt.timedelta(days=1)).isoformat()
    r = client.post("/api/sessions", json={"date": tomorrow, "title": "Future", "workout_template_id": None})
    assert r.status_code == 422