from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session as DBSession, select
import httpx

from ..db import get_session
from ..models import Exercise, Muscle, ExerciseMuscle, Category
from ..services.adapters.wger import search_wger, browse_wger
from ..schemas import ExerciseRead

router = APIRouter(prefix="/api/external", tags=["external"])

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
    # Validate muscle slug early so the UI gets a clear 400 if it sends 'delts' by mistake.
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

    # Also return next_offset to help the UI paginate (simple client-side paging helper)
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
        # Network/HTTP problems to WGER
        raise HTTPException(status_code=502, detail=f"WGER HTTP error: {e!s}")
    except Exception as e:
        # Any other bug (parsing, KeyError, etc.)
        raise HTTPException(status_code=500, detail=f"Adapter error: {type(e).__name__}: {e}")


@router.post("/exercises/import", response_model=ExerciseRead, status_code=201)
def import_exercise(payload: dict, session: DBSession = Depends(get_session)):
    """
    Accept a normalized object like:
    {
      "source":"wger","source_ref":"1234","name":"Barbell Squat",
      "category":"strength","default_unit":"kg","equipment":null,
      "muscles":{"primary":["quads"], "secondary":["glutes","hams"]}
    }
    """
    name = " ".join((payload.get("name") or "").split())
    if not name:
        raise HTTPException(status_code=400, detail="name required")

    # dedupe by (source, source_ref) or by name
    src = payload.get("source") or "wger"
    src_ref = payload.get("source_ref") or None
    if src_ref:
        dup = session.exec(
            select(Exercise).where(Exercise.source == src, Exercise.source_ref == str(src_ref))
        ).first()
        if dup:
            return dup

    dup2 = session.exec(select(Exercise).where(Exercise.name == name)).first()
    if dup2:
        return dup2

    # ensure muscles exist
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

    # category validation with friendly error if invalid enum value
    raw_cat = (payload.get("category") or "strength")
    try:
        cat = Category(raw_cat)
    except Exception:
        raise HTTPException(status_code=400, detail=f"Invalid category '{raw_cat}'")

    # create exercise
    ex = Exercise(
        name=name,
        category=cat,
        default_unit=payload.get("default_unit"),
        equipment=payload.get("equipment"),
        source=src,
        source_ref=str(src_ref) if src_ref else None,
    )
    session.add(ex)
    session.commit()
    session.refresh(ex)

    # link muscles
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