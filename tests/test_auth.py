def test_register_login_me_logout_flow(client):
    # Register
    r = client.post(
        "/api/auth/register",
        json={"email": "alice@example.com", "password": "secret123"},
    )
    assert r.status_code in (200, 201)
    data = r.json()
    assert "email" in data

    # Login
    r = client.post(
        "/api/auth/login", json={"email": "alice@example.com", "password": "secret123"}
    )
    assert r.status_code == 200
    assert "access_token" in client.cookies  # cookie should be set

    # Me
    r = client.get("/api/auth/me")
    assert r.status_code == 200
    me = r.json()
    assert me["email"] == "alice@example.com"

    # Logout
    r = client.post("/api/auth/logout")
    assert r.status_code in (200, 204)

    # Me should now be unauthorized
    r = client.get("/api/auth/me")
    assert r.status_code == 401


def _register_and_login(client, email="isotest@example.com", password="secret123"):
    r = client.post("/api/auth/register", json={"email": email, "password": password})
    assert r.status_code in (200, 201)
    r = client.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200


def test_me_unauthorized_without_cookie(client):
    r = client.get("/api/auth/me")
    assert r.status_code == 401


def test_login_bad_credentials(client):
    # register a user
    client.post(
        "/api/auth/register", json={"email": "bad@ex.com", "password": "goodpass"}
    )
    # wrong password
    r = client.post(
        "/api/auth/login", json={"email": "bad@ex.com", "password": "WRONG"}
    )
    assert r.status_code == 401


def test_per_user_isolation_on_exercises(client):
    # Alice creates one exercise
    _register_and_login(client, "alice@ex.com", "pw123456")
    r = client.post(
        "/api/exercises", json={"name": "Alice Only Curl", "category": "strength"}
    )
    assert r.status_code in (200, 201)

    # Logout and login as Bob
    client.post("/api/auth/logout")
    _register_and_login(client, "bob@ex.com", "pw123456")

    # Bob should NOT see Alice's exercise
    r = client.get("/api/exercises?limit=100")
    assert r.status_code == 200
    names = [e["name"] for e in r.json()]
    assert "Alice Only Curl" not in names


def test_logout_clears_cookie_and_me_requires_auth(client):
    # Register + login
    client.post(
        "/api/auth/register", json={"email": "bob@example.com", "password": "secret123"}
    )
    r = client.post(
        "/api/auth/login", json={"email": "bob@example.com", "password": "secret123"}
    )
    assert r.status_code == 200
    assert (
        "access_token" in client.cookies or "session" in client.cookies
    )  # support either name

    # /me works while logged in
    r = client.get("/api/auth/me")
    assert r.status_code == 200

    # logout
    client.post("/api/auth/logout")

    # cookie should be gone
    assert "access_token" not in client.cookies and "session" not in client.cookies

    # /me should be unauthorized now
    r = client.get("/api/auth/me")
    assert r.status_code == 401


def test_me_with_bad_token_returns_401(client):
    # set a bad token name for either cookie name your app uses
    client.cookies.set(
        "access_token", "definitely.not.valid", domain="testserver.local", path="/"
    )
    client.cookies.set(
        "session", "definitely.not.valid", domain="testserver.local", path="/"
    )
    r = client.get("/api/auth/me")
    assert r.status_code == 401


def test_html_pages_require_auth(client):
    # Unauthed index should be 401 (your Depends(get_current_user))
    r = client.get("/")
    assert r.status_code == 401

    # Login
    client.post(
        "/api/auth/register", json={"email": "hp@example.com", "password": "secret123"}
    )
    client.post(
        "/api/auth/login", json={"email": "hp@example.com", "password": "secret123"}
    )

    # Now index is allowed
    r = client.get("/")
    assert r.status_code == 200
