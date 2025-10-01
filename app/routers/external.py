from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlmodel import Session as DBSession, select
import httpx

from ..db import get_session
from ..auth import get_current_user
from ..models import Exercise, Muscle, ExerciseMuscle, Category, User
from ..services.adapters.wger import search_wger, browse_wger
from ..schemas import ExerciseRead

router = APIRouter(prefix="/api/external", tags=["external"])

def ensure_owner(obj, user_id: int, what: str = "resource"):
    if not obj or getattr(obj, "user_id", None) != user_id:
        raise HTTPException(status_code=404, detail=f"{what} not found")

# IMPORTANT: these slugs must match muscles_map_wger() in the WGER adapter
MUSCLES = [
    {"slug": "biceps",       "label": "Biceps"},
    {"slug": "triceps",      "label": "Triceps"},
    {"slug": "chest",        "label": "Chest"},
    {"slug": "lats",         "label": "Lats / Back"},
    {"slug": "traps",        "label": "Trapezius"},
    {"slug": "lower_back",   "label": "Lower Back"},
    {"slug": "quads",        "label": "Quads"},
    {"slug": "hams",         "label": "Hamstrings"},
    {"slug": "glutes",       "label": "Glutes"},
    {"slug": "calves",       "label": "Calves"},
    {"slug": "front_delts",  "label": "Front Delts"},
    {"slug": "side_delts",   "label": "Side Delts"},
    {"slug": "abs",          "label": "Abs / Core"},
]

@router.get("/muscles")
def list_muscles():
    """Return the list of valid muscle slugs for filtering/badges in the UI."""
    return MUSCLES

@router.get("/exercises/browse")
async def external_browse(
    muscle: str | None = Query(
        None,
        description="Optional muscle slug (e.g. 'quads', 'front_delts'). Must match /api/external/muscles.",
    ),
    limit: int = Query(20, ge=1, le=50),
    offset: int = Query(0, ge=0),
):
    """
    Browse WGER exercises (enriched) with optional muscle filtering.
    'muscle' must be one of the slugs from /api/external/muscles.
    """
    valid_slugs = {m["slug"] for m in MUSCLES}
    if muscle is not None and muscle not in valid_slugs:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid muscle slug '{muscle}'. Valid options: {sorted(valid_slugs)}",
        )

    try:
        items = await browse_wger(limit=limit, offset=offset, muscle=muscle)
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"WGER HTTP error: {e!s}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Adapter error: {type(e).__name__}: {e}")

    next_offset = offset + limit if len(items) == limit else None
    return {"items": items, "limit": limit, "offset": offset, "next_offset": next_offset}

@router.get("/exercises")
async def external_search(
    q: str = Query(..., min_length=2, description="Name query, e.g. 'leg press'"),
    limit: int = Query(20, ge=1, le=50),
):
    """
    Strict token-AND name search against WGER (post-enrichment), ranked by token/phrase quality.
    """
    try:
        results = await search_wger(q, limit=limit)
        return results
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"WGER HTTP error: {e!s}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Adapter error: {type(e).__name__}: {e}")

@router.post("/exercises/import", response_model=ExerciseRead, status_code=201)
def import_exercise(
    payload: dict,
    session: DBSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """
    Accept a normalized object like:
    {
      "source":"wger","source_ref":"1234","name":"Barbell Squat",
      "category":"strength","default_unit":"kg","equipment":null,
      "muscles":{"primary":["quads"], "secondary":["glutes","hams"]}
    }
    Creates the exercise for the CURRENT USER only, and de-dupes per user.
    """
    name = " ".join((payload.get("name") or "").split())
    if not name:
        raise HTTPException(status_code=400, detail="name required")

    src = (payload.get("source") or "wger").strip().lower()
    src_ref = (str(payload.get("source_ref")).strip() or None)

    # ----- De-dupe PER USER -----
    #Prefer (source, source_ref, user_id)
    if src_ref:
        dup = session.exec(
            select(Exercise).where(
                Exercise.user_id == user.id,
                Exercise.source == src,
                Exercise.source_ref == src_ref,
            )
        ).first()
        if dup:
            return dup

    # Fallback: name (case-insensitive) per user
    dup2 = session.exec(
        select(Exercise).where(
            Exercise.user_id == user.id,
            func.lower(Exercise.name) == name.lower(),
        )
    ).first()
    if dup2:
        return dup2

    # ----- Ensure muscles exist -----
    muscles = payload.get("muscles") or {}
    slugs = set((muscles.get("primary") or []) + (muscles.get("secondary") or []))
    existing = {m.slug: m for m in session.exec(select(Muscle)).all()}
    for slug in slugs:
        if slug and slug not in existing:
            m = Muscle(name=slug.replace("_", " ").title(), slug=slug)
            session.add(m)
            session.commit()
            session.refresh(m)
            existing[slug] = m

    # ----- Category enum validation -----
    raw_cat = (payload.get("category") or "strength")
    try:
        cat = Category(raw_cat)
    except Exception:
        raise HTTPException(status_code=400, detail=f"Invalid category '{raw_cat}'")

    # ----- Create exercise FOR THIS USER -----
    ex = Exercise(
        user_id=user.id,
        name=name,
        category=cat,
        default_unit=payload.get("default_unit"),
        equipment=payload.get("equipment"),
        source=src,
        source_ref=src_ref,
    )
    session.add(ex)
    session.commit()
    session.refresh(ex)

    # ----- Link muscles to this exercise -----
    for slug in (muscles.get("primary") or []):
        m = existing.get(slug)
        if m:
            session.add(ExerciseMuscle(exercise_id=ex.id, muscle_id=m.id, role="primary"))  # type: ignore
    for slug in (muscles.get("secondary") or []):
        m = existing.get(slug)
        if m:
            session.add(ExerciseMuscle(exercise_id=ex.id, muscle_id=m.id, role="secondary"))  # type: ignore
    session.commit()

    return ex

@router.get("/ping")
def ping():
    return {"ok": True}