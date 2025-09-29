from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session as DBSession, select

from ..db import get_session
from ..auth import get_current_user
from ..models import Exercise, WorkoutItem, SessionItem, Category, WorkoutTemplate, Session, ExerciseMuscle, User

from ..schemas import ExerciseCreate, ExerciseRead, ExerciseUpdate

router = APIRouter(prefix="/api/exercises", tags=["exercises"])

def ensure_owner(obj, user_id: int, what: str = "resource"):
    if not obj or getattr(obj, "user_id", None) != user_id:
        raise HTTPException(status_code=404, detail=f"{what} not found")

def _norm(s: Optional[str]) -> Optional[str]:
    if s is None:
        return None
    return " ".join(s.strip().split()) or None

def _case_insensitive_equal(a: str, b: str) -> bool:
    return a.casefold() == b.casefold()

@router.post("", response_model=ExerciseRead, status_code=201)
def create_exercise(
    payload: ExerciseCreate,
    db: DBSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    if not payload.name or not payload.name.strip():
        raise HTTPException(status_code=400, detail="Name is required")

    norm_name = _norm(payload.name)

    # case-insensitive uniqueness PER USER
    dup = db.exec(
        select(Exercise)
        .where(Exercise.user_id == user.id)
        .where(func.lower(Exercise.name) == norm_name.lower())
    ).first()
    if dup:
        raise HTTPException(status_code=409, detail="Exercise with that name already exists")

    ex = Exercise(
        user_id=user.id,
        name=norm_name,
        category=payload.category,
        default_unit=_norm(payload.default_unit),
        equipment=_norm(payload.equipment),
        source="local",
        source_ref=None,
    )
    db.add(ex)
    db.commit()
    db.refresh(ex)
    return ex

@router.get("", response_model=List[ExerciseRead])
def list_exercises(
    db: DBSession = Depends(get_session),
    user: User = Depends(get_current_user),
    q: Optional[str] = Query(None, description="Substring name match (case-insensitive)"),
    category: Optional[Category] = Query(None, description="Category filter"),
    limit: int = Query(100, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    stmt = select(Exercise).where(Exercise.user_id == user.id)
    if q:
        stmt = stmt.where(func.lower(Exercise.name).like(f"%{q.lower()}%"))
    if category is not None:
        stmt = stmt.where(Exercise.category == category)

    # Keep predictable order: newest first (id desc). Change if you prefer created_at.
    stmt = stmt.order_by(Exercise.id.desc())
    stmt = stmt.limit(limit).offset(offset)
    return db.exec(stmt).all()

@router.get("/{exercise_id}", response_model=ExerciseRead)
def get_exercise(
    exercise_id: int,
    db: DBSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    ex = db.get(Exercise, exercise_id)
    ensure_owner(ex, user.id, "exercise")
    return ex

@router.put("/{exercise_id}", response_model=ExerciseRead)
def update_exercise(
    exercise_id: int,
    payload: ExerciseUpdate,
    db: DBSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    ex = db.get(Exercise, exercise_id)
    ensure_owner(ex, user.id, "exercise")

    data = payload.model_dump(exclude_unset=True)

    if "name" in data and data["name"] is not None:
        new_name = _norm(data["name"])
        if not new_name:
            raise HTTPException(status_code=400, detail="Name cannot be empty")
        if not _case_insensitive_equal(new_name, ex.name):
            dup = db.exec(
                select(Exercise)
                .where(Exercise.user_id == user.id)
                .where(func.lower(Exercise.name) == new_name.lower())
            ).first()
            if dup:
                raise HTTPException(status_code=409, detail="Exercise with that name already exists")
        ex.name = new_name

    if "category" in data:
        ex.category = data["category"] or ex.category
    if "default_unit" in data:
        ex.default_unit = _norm(data["default_unit"])
    if "equipment" in data:
        ex.equipment = _norm(data["equipment"])

    db.add(ex)
    db.commit()
    db.refresh(ex)
    return ex

@router.delete("/{exercise_id}", status_code=204)
def delete_exercise(
    exercise_id: int,
    db: DBSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    ex = db.get(Exercise, exercise_id)
    ensure_owner(ex, user.id, "exercise")

    try:
        # remove muscle links first
        links = db.exec(
            select(ExerciseMuscle).where(ExerciseMuscle.exercise_id == exercise_id)
        ).all()
        for link in links:
            db.delete(link)
        db.flush()

        db.delete(ex)
        db.commit()
        return None
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot delete exercise: it is referenced by workouts/sessions.",
        )

@router.get("/{exercise_id}/usage")
def get_exercise_usage(
    exercise_id: int,
    db: DBSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    ex = db.get(Exercise, exercise_id)
    ensure_owner(ex, user.id, "exercise")

    wq = (
        select(WorkoutTemplate)
        .where(WorkoutTemplate.user_id == user.id)
        .join(WorkoutItem, WorkoutItem.workout_template_id == WorkoutTemplate.id)
        .where(WorkoutItem.exercise_id == exercise_id)
        .order_by(WorkoutTemplate.name.asc())
    )
    workouts = db.exec(wq).all()

    sq = (
        select(Session)
        .where(Session.user_id == user.id)
        .join(SessionItem, SessionItem.session_id == Session.id)
        .where(SessionItem.exercise_id == exercise_id)
        .order_by(Session.date.desc())
    )
    sessions_rows = db.exec(sq).all()

    return {
        "exercise": {"id": ex.id, "name": ex.name},
        "workouts": [{"id": w.id, "name": w.name} for w in workouts],
        "sessions": [{"id": s.id, "title": s.title, "date": str(s.date)} for s in sessions_rows],
        "counts": {"workouts": len(workouts), "sessions": len(sessions_rows)},
    }