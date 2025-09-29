# tests/test_auth.py
def test_register_login_me_logout_flow(client):
    # Register
    r = client.post("/api/auth/register", json={"email": "alice@example.com", "password": "secret123"})
    assert r.status_code in (200, 201)
    data = r.json()
    assert "email" in data

    # Login
    r = client.post("/api/auth/login", json={"email": "alice@example.com", "password": "secret123"})
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