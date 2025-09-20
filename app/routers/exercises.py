from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select
from sqlalchemy import func

from ..db import get_session
from ..models import Exercise, Workout
from ..schemas import ExerciseCreate, ExerciseRead, ExerciseUpdate

router = APIRouter(prefix="/exercises", tags=["exercises"])

def _norm_name(name: str) -> str:
    # normalize for comparisons and storage 
    return " ".join(name.strip().split())

def _case_insensitive_equal(a: str, b: str) -> bool:
    return a.casefold() == b.casefold()

@router.post("", response_model=ExerciseRead, status_code=201)
def create_exercise(payload: ExerciseCreate, session: Session = Depends(get_session)):
    # validate basic name
    if not payload.name or not payload.name.strip():
        raise HTTPException(status_code=400, detail="Name is required")

    norm_name = _norm_name(payload.name)

    # case-insensitive uniqueness check
    dup = session.exec(
        select(Exercise).where(func.lower(Exercise.name) == norm_name.lower())
    ).first()
    if dup:
        raise HTTPException(status_code=409, detail="Exercise with that name already exists")

    ex = Exercise(
        name=norm_name,
        category=payload.category.strip() if payload.category else None,
        default_unit=payload.default_unit.strip() if payload.default_unit else None,
    )
    session.add(ex)
    session.commit()
    session.refresh(ex)
    return ex

@router.get("", response_model=List[ExerciseRead])
def list_exercises(
    session: Session = Depends(get_session),
    q: Optional[str] = Query(None, description="Substring match on name (case-insensitive)"),
    category: Optional[str] = Query(None, description="Category filter (case-insensitive partial)"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    sort: str = Query("name", pattern="^(name|id)$"), 
):
    stmt = select(Exercise)

    if q:
        stmt = stmt.where(func.lower(Exercise.name).like(f"%{q.lower()}%"))
    if category:
        stmt = stmt.where(func.lower(Exercise.category).like(f"%{category.lower()}%"))

    # order
    if sort == "name":
        stmt = stmt.order_by(Exercise.name.asc())
    else:
        stmt = stmt.order_by(Exercise.id.asc())

    # pagination
    stmt = stmt.limit(limit).offset(offset)

    return session.exec(stmt).all()

@router.get("/{exercise_id}", response_model=ExerciseRead)
def get_exercise(exercise_id: int, session: Session = Depends(get_session)):
    ex = session.get(Exercise, exercise_id)
    if not ex:
        raise HTTPException(status_code=404, detail="Exercise not found")
    return ex

@router.put("/{exercise_id}", response_model=ExerciseRead)
def update_exercise(exercise_id: int, payload: ExerciseUpdate, session: Session = Depends(get_session)):
    ex = session.get(Exercise, exercise_id)
    if not ex:
        raise HTTPException(status_code=404, detail="Exercise not found")

    data = payload.model_dump(exclude_unset=True)

    # name: normalize + case-insensitive uniqueness
    if "name" in data and data["name"] is not None:
        new_name = _norm_name(data["name"])
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
        ex.category = data["category"].strip() if data["category"] else None
    if "default_unit" in data:
        ex.default_unit = data["default_unit"].strip() if data["default_unit"] else None

    session.add(ex)
    session.commit()
    session.refresh(ex)
    return ex

@router.delete("/{exercise_id}", status_code=204)
def delete_exercise(exercise_id: int, session: Session = Depends(get_session)):
    ex = session.get(Exercise, exercise_id)
    if not ex:
        raise HTTPException(status_code=404, detail="Exercise not found")

    # prevent deleting exercises in use 
    in_use = session.exec(
        select(Workout.id).where(Workout.exercise_id == exercise_id).limit(1)
    ).first()
    if in_use:
        raise HTTPException(
            status_code=409,
            detail="Cannot delete exercise: there are workouts using it. Reassign or delete those workouts first."
        )

    session.delete(ex)
    session.commit()
    return None