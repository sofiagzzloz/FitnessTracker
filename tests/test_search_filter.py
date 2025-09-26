from app.services.adapters.wger import _filter_and_rank

def _mk(name): return {"name": name, "id": hash(name) & 0xffff}

def test_and_tokens():
    items = [_mk("Leg Press Machine"), _mk("Leg Curl"), _mk("Single-Leg Press"), _mk("Press Overhead")]
    out = _filter_and_rank(items, "leg press", cap=10)
    names = [x["name"] for x in out]
    assert "Leg Press Machine" in names
    assert "Single-Leg Press" in names
    assert "Leg Curl" not in names
    assert "Press Overhead" not in names

def test_plural_accents_punct():
    items = [_mk("Front Squat"), _mk("Sumo Squats"), _mk("Squat (Barbell)"), _mk("Hip Thrust")]
    out = _filter_and_rank(items, "squats", cap=10)
    names = [x["name"] for x in out]
    assert "Front Squat" in names
    assert "Sumo Squats" in names
    assert "Squat (Barbell)" in names
    assert "Hip Thrust" not in names