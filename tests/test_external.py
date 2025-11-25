import httpx
import pytest

from app.routers import external as external_router


def _register_and_login(client, email="ext@example.com"):
    payload = {"email": email, "password": "secret123"}
    assert client.post("/api/auth/register", json=payload).status_code in (200, 201)
    assert client.post("/api/auth/login", json=payload).status_code == 200


def test_list_muscles_reports_known_slug(client):
    resp = client.get("/api/external/muscles")
    assert resp.status_code == 200
    slugs = {m["slug"] for m in resp.json()}
    assert "quads" in slugs


def test_external_browse_rejects_bad_slug(client):
    resp = client.get(
        "/api/external/exercises/browse", params={"muscle": "invalid-muscle"}
    )
    assert resp.status_code == 400


def test_external_browse_uses_adapter(monkeypatch, client):
    async def fake_browse_wger(*, limit: int, offset: int, muscle: str | None):
        assert limit == 5
        assert offset == 0
        assert muscle is None
        return [
            {
                "name": "Sample Lift",
                "category": "strength",
                "muscles": {"primary": ["quads"], "secondary": []},
            }
        ]

    monkeypatch.setattr(external_router, "browse_wger", fake_browse_wger)

    resp = client.get("/api/external/exercises/browse", params={"limit": 5, "offset": 0})
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["items"][0]["name"] == "Sample Lift"
    assert payload["next_offset"] is None


def test_external_search_handles_http_errors(monkeypatch, client):
    async def failing_search(*args, **kwargs):
        raise httpx.HTTPError("boom")

    monkeypatch.setattr(external_router, "search_wger", failing_search)
    resp = client.get("/api/external/exercises", params={"q": "press"})
    assert resp.status_code == 502


def test_external_search_returns_results(monkeypatch, client):
    async def fake_search(q: str, limit: int):
        assert q == "press"
        assert limit == 3
        return [
            {"name": "Chest Press", "source": "wger", "muscles": {"primary": []}}
        ]

    monkeypatch.setattr(external_router, "search_wger", fake_search)
    resp = client.get("/api/external/exercises", params={"q": "press", "limit": 3})
    assert resp.status_code == 200
    assert resp.json()[0]["name"] == "Chest Press"


def test_import_exercise_dedupes_by_source_and_name(client):
    _register_and_login(client)

    payload = {
        "source": "wger",
        "source_ref": "123",
        "name": "Barbell Squat",
        "category": "strength",
        "default_unit": "kg",
        "equipment": None,
        "muscles": {"primary": ["quads"], "secondary": ["glutes"]},
    }

    first = client.post("/api/external/exercises/import", json=payload)
    assert first.status_code == 201
    first_id = first.json()["id"]

    dup_same_ref = client.post("/api/external/exercises/import", json=payload)
    assert dup_same_ref.status_code in (200, 201)
    assert dup_same_ref.json()["id"] == first_id

    # Drop the source ref to trigger name-based dedupe
    payload["source_ref"] = None
    dup_same_name = client.post("/api/external/exercises/import", json=payload)
    assert dup_same_name.status_code in (200, 201)
    assert dup_same_name.json()["id"] == first_id

    exercises = client.get("/api/exercises").json()
    assert any(e["name"] == "Barbell Squat" for e in exercises)


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("Running!!!", "cardio"),
        ("Bench Press", "strength"),
    ],
)
def test_category_helpers_cover_edge_cases(raw, expected):
    from app.services.adapters import wger as wger_adapter

    assert wger_adapter.category_for(raw) == expected
    assert wger_adapter._norm(raw)
    assert wger_adapter._tokens(raw)

    name_score = wger_adapter._score_name("Bench Press", ["bench", "press"])
    assert name_score[0] >= 0

    sample = {
        "results": [
            {"exercise": 1, "name": "  Bench Press "},
            {"exercise": 1, "name": "Duplicate"},
            {"exercise": 2, "name": None},
        ]
    }
    cand = wger_adapter._cand_from_translation(sample)
    assert cand == [(1, "Bench Press")]
