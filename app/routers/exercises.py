# app/routers/exercises.py
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session as DBSession, select, delete

from ..db import get_session
from ..auth import get_current_user
from ..models import (
    Exercise,
    WorkoutItem,
    WorkoutTemplate,
    Session,
    SessionItem,
    ExerciseMuscle,
    Category,
    User,
)
from ..schemas import ExerciseCreate, ExerciseRead, ExerciseUpdate

router = APIRouter(prefix="/api/exercises", tags=["exercises"])

# ---------- ownership helpers ----------
def ensure_owner(obj, user_id: int, what: str = "resource"):
    """404 if missing or owned by someone else (only enforces if model has user_id)."""
    if not obj:
        raise HTTPException(status_code=404, detail=f"{what} not found")
    if hasattr(obj, "user_id") and getattr(obj, "user_id") != user_id:
        # 404 to avoid leaking existence
        raise HTTPException(status_code=404, detail=f"{what} not found")

def add_owner_filter(stmt, model, user_id: int):
    """If a model has user_id, add WHERE user_id=:user_id; otherwise no-op."""
    if hasattr(model, "user_id"):
        return stmt.where(getattr(model, "user_id") == user_id)
    return stmt

# ---------- misc helpers ----------
def _norm(s: Optional[str]) -> Optional[str]:
    if s is None:
        return None
    return " ".join(s.strip().split()) or None

def _case_insensitive_equal(a: str, b: str) -> bool:
    return a.casefold() == b.casefold()

# ---------- create ----------
@router.post("", response_model=ExerciseRead, status_code=201)
def create_exercise(
    payload: ExerciseCreate,
    session: DBSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    if not payload.name or not payload.name.strip():
        raise HTTPException(status_code=400, detail="Name is required")

    norm_name = _norm(payload.name)
    if not norm_name:
        raise HTTPException(status_code=400, detail="Name is required")

    # uniqueness (global or per-user depending on presence of user_id column)
    stmt = select(Exercise).where(func.lower(Exercise.name) == norm_name.lower())
    stmt = add_owner_filter(stmt, Exercise, user.id)
    dup = session.exec(stmt).first()
    if dup:
        raise HTTPException(status_code=409, detail="Exercise with that name already exists")

    data = dict(
        name=norm_name,
        category=payload.category,
        default_unit=_norm(payload.default_unit),
        equipment=_norm(payload.equipment),
        source="local",
        source_ref=None,
    )
    if hasattr(Exercise, "user_id"):
        data["user_id"] = user.id

    ex = Exercise(**data)
    session.add(ex)
    session.commit()
    session.refresh(ex)
    return ex

# ---------- list ----------
@router.get("", response_model=List[ExerciseRead])
def list_exercises(
    db: DBSession = Depends(get_session),
    user: User = Depends(get_current_user),
    q: Optional[str] = Query(None, description="Substring name match (case-insensitive)"),
    category: Optional[Category] = Query(None, description="Category filter"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    # IMPORTANT: default to "id" (chronological), not "name"
    sort: str = Query("id", pattern="^(name|id)$"),
):
    stmt = select(Exercise).where(Exercise.user_id == user.id)
    if q:
        stmt = stmt.where(func.lower(Exercise.name).like(f"%{q.lower()}%"))
    if category is not None:
        stmt = stmt.where(Exercise.category == category)

    # stable chronological order
    if sort == "name":
        stmt = stmt.order_by(func.lower(Exercise.name).asc(), Exercise.id.asc())
    else:
        stmt = stmt.order_by(Exercise.id.asc())

    stmt = stmt.limit(limit).offset(offset)
    return db.exec(stmt).all()

# ---------- get one ----------
@router.get("/{exercise_id}", response_model=ExerciseRead)
def get_exercise(
    exercise_id: int,
    session: DBSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    ex = session.get(Exercise, exercise_id)
    ensure_owner(ex, user.id, "exercise")
    return ex

# ---------- update ----------
@router.put("/{exercise_id}", response_model=ExerciseRead)
def update_exercise(
    exercise_id: int,
    payload: ExerciseUpdate,
    session: DBSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    ex = session.get(Exercise, exercise_id)
    ensure_owner(ex, user.id, "exercise")

    data = payload.model_dump(exclude_unset=True)

    # name: normalize + uniqueness within the same owner scope
    if "name" in data and data["name"] is not None:
        new_name = _norm(data["name"])
        if not new_name:
            raise HTTPException(status_code=400, detail="Name cannot be empty")

        if not _case_insensitive_equal(new_name, ex.name):
            stmt = select(Exercise).where(func.lower(Exercise.name) == new_name.lower())
            stmt = add_owner_filter(stmt, Exercise, user.id)
            dup = session.exec(stmt).first()
            if dup:
                raise HTTPException(status_code=409, detail="Exercise with that name already exists")
        ex.name = new_name

    if "category" in data and data["category"] is not None:
        ex.category = data["category"]
    if "default_unit" in data:
        ex.default_unit = _norm(data["default_unit"])
    if "equipment" in data:
        ex.equipment = _norm(data["equipment"])

    session.add(ex)
    session.commit()
    session.refresh(ex)
    return ex

# ---------- delete ----------
@router.delete("/{exercise_id}", status_code=204)
def delete_exercise(
    exercise_id: int,
    session: DBSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    ex = session.get(Exercise, exercise_id)
    ensure_owner(ex, user.id, "exercise")

    try:
        # detach muscle links first
        links = session.exec(
            select(ExerciseMuscle).where(ExerciseMuscle.exercise_id == exercise_id)
        ).all()
        for link in links:
            session.delete(link)
        session.flush()

        # attempt delete; FK references (workouts/sessions) will raise IntegrityError
        session.delete(ex)
        session.commit()
        return None

    except IntegrityError:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot delete exercise: it is referenced by workouts/sessions.",
        )

# ---------- usage ----------
@router.get("/{exercise_id}/usage")
def get_exercise_usage(
    exercise_id: int,
    session: DBSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    ex = session.get(Exercise, exercise_id)
    ensure_owner(ex, user.id, "exercise")

    # Workouts that use this exercise (limit to user's templates if user_id exists)
    wq = (
        select(WorkoutTemplate)
        .join(WorkoutItem, WorkoutItem.workout_template_id == WorkoutTemplate.id)
        .where(WorkoutItem.exercise_id == exercise_id)
        .order_by(WorkoutTemplate.name.asc())
    )
    wq = add_owner_filter(wq, WorkoutTemplate, user.id)
    workouts = session.exec(wq).all()

    # Sessions that used this exercise (limit to user's sessions if user_id exists)
    sq = (
        select(Session)
        .join(SessionItem, SessionItem.session_id == Session.id)
        .where(SessionItem.exercise_id == exercise_id)
        .order_by(Session.date.desc(), Session.id.desc())
    )
    sq = add_owner_filter(sq, Session, user.id)
    sessions_rows = session.exec(sq).all()

    return {
        "exercise": {"id": ex.id, "name": ex.name},
        "workouts": [{"id": w.id, "name": w.name} for w in workouts],
        "sessions": [{"id": s.id, "title": s.title, "date": str(s.date)} for s in sessions_rows],
        "counts": {"workouts": len(workouts), "sessions": len(sessions_rows)},
    }