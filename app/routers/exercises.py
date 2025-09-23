from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select as DBSession, select
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from fastapi import status

from ..db import get_session
from ..models import Exercise, WorkoutItem, SessionItem, Category, WorkoutTemplate, Session, ExerciseMuscle
from ..schemas import ExerciseCreate, ExerciseRead, ExerciseUpdate

router = APIRouter(prefix="/api/exercises", tags=["exercises"])


# ---------- helpers ----------
def _norm(s: Optional[str]) -> Optional[str]:
    if s is None:
        return None
    return " ".join(s.strip().split()) or None


def _case_insensitive_equal(a: str, b: str) -> bool:
    return a.casefold() == b.casefold()


# ---------- create ----------
@router.post("", response_model=ExerciseRead, status_code=201)
def create_exercise(payload: ExerciseCreate, session: Session = Depends(get_session)):
    if not payload.name or not payload.name.strip():
        raise HTTPException(status_code=400, detail="Name is required")

    norm_name = _norm(payload.name)

    # case-insensitive uniqueness
    dup = session.exec(
        select(Exercise).where(func.lower(Exercise.name) == norm_name.lower())
    ).first()
    if dup:
        raise HTTPException(status_code=409, detail="Exercise with that name already exists")

    ex = Exercise(
        name=norm_name,
        category=payload.category,  # pydantic enum validated
        default_unit=_norm(payload.default_unit),
        equipment=_norm(payload.equipment),
        source="local",
        source_ref=None,
    )
    session.add(ex)
    session.commit()
    session.refresh(ex)
    return ex


# ---------- list ----------
@router.get("", response_model=List[ExerciseRead])
def list_exercises(
    session: DBSession = Depends(get_session),
    q: Optional[str] = Query(None, description="Substring name match (case-insensitive)"),
    category: Optional[Category] = Query(None, description="Category filter"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    sort: str = Query("name", pattern="^(name|id)$"),
):
    stmt = select(Exercise)

    if q:
        stmt = stmt.where(func.lower(Exercise.name).like(f"%{q.lower()}%"))
    if category is not None:
        stmt = stmt.where(Exercise.category == category)

    stmt = stmt.order_by(Exercise.name.asc() if sort == "name" else Exercise.id.asc())
    stmt = stmt.limit(limit).offset(offset)

    return session.exec(stmt).all()


# ---------- get one ----------
@router.get("/{exercise_id}", response_model=ExerciseRead)
def get_exercise(exercise_id: int, session: DBSession = Depends(get_session)):
    ex = session.get(Exercise, exercise_id)
    if not ex:
        raise HTTPException(status_code=404, detail="Exercise not found")
    return ex


# ---------- update ----------
@router.put("/{exercise_id}", response_model=ExerciseRead)
def update_exercise(exercise_id: int, payload: ExerciseUpdate, session: Session = Depends(get_session)):
    ex = session.get(Exercise, exercise_id)
    if not ex:
        raise HTTPException(status_code=404, detail="Exercise not found")

    data = payload.model_dump(exclude_unset=True)

    # name: normalize + uniqueness
    if "name" in data and data["name"] is not None:
        new_name = _norm(data["name"])
        if not new_name:
            raise HTTPException(status_code=400, detail="Name cannot be empty")
        if not _case_insensitive_equal(new_name, ex.name):
            dup = session.exec(
                select(Exercise).where(func.lower(Exercise.name) == new_name.lower())
            ).first()
            if dup:
                raise HTTPException(status_code=409, detail="Exercise with that name already exists")
        ex.name = new_name

    if "category" in data:
        # pydantic already validated enum if provided
        ex.category = data["category"] or ex.category
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
def delete_exercise(exercise_id: int, session: Session = Depends(get_session)):
    ex = session.get(Exercise, exercise_id)
    if not ex:
        raise HTTPException(status_code=404, detail="Exercise not found")

    try:
        # 1) Detach muscle links so they don't block deletion
        links = session.exec(
            select(ExerciseMuscle).where(ExerciseMuscle.exercise_id == exercise_id)
        ).all()
        for link in links:
            session.delete(link)
        session.flush()  # keep in same transaction

        # 2) Try deleting the exercise; workouts/sessions will still block with FK 409
        session.delete(ex)
        session.commit()
        return None

    except IntegrityError:
        session.rollback()
        # Still referenced by workouts/sessions (that's expected to block)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot delete exercise: it is referenced by workouts/sessions."
        )

@router.get("/{exercise_id}/usage")
def get_exercise_usage(exercise_id: int, session: Session = Depends(get_session)):
    ex = session.get(Exercise, exercise_id)
    if not ex:
        raise HTTPException(status_code=404, detail="Exercise not found")

    # Workouts (WorkoutTemplate + WorkoutItem)
    wq = (
        select(WorkoutTemplate)
        .join(WorkoutItem, WorkoutItem.workout_template_id == WorkoutTemplate.id)
        .where(WorkoutItem.exercise_id == exercise_id)
        .order_by(WorkoutTemplate.name.asc())
    )
    workouts = session.exec(wq).all()

    # Sessions (Session + SessionItem)
    sq = (
        select(Session)
        .join(SessionItem, SessionItem.session_id == Session.id)
        .where(SessionItem.exercise_id == exercise_id)
        .order_by(Session.date.desc())
    )
    sessions_rows = session.exec(sq).all()

    return {
        "exercise": {"id": ex.id, "name": ex.name},
        "workouts": [{"id": w.id, "name": w.name} for w in workouts],
        "sessions": [{"id": s.id, "title": s.title, "date": str(s.date)} for s in sessions_rows],
        "counts": {"workouts": len(workouts), "sessions": len(sessions_rows)},
    }