from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select

from ..db import get_session
from ..models import Exercise
from ..schemas import ExerciseCreate, ExerciseRead, ExerciseUpdate

router = APIRouter(prefix="/exercises", tags=["exercises"])

@router.post("", response_model=ExerciseRead, status_code=201)
def create_exercise(payload: ExerciseCreate, session: Session = Depends(get_session)):
    # optional: enforce unique name
    exists = session.exec(select(Exercise).where(Exercise.name == payload.name)).first()
    if exists:
        raise HTTPException(status_code=409, detail="Exercise with that name already exists")

    ex = Exercise(**payload.model_dump())
    session.add(ex)
    session.commit()
    session.refresh(ex)
    return ex

@router.get("", response_model=List[ExerciseRead])
def list_exercises(
    session: Session = Depends(get_session),
    q: Optional[str] = Query(None, description="Substring match on name"),
    category: Optional[str] = Query(None),
):
    stmt = select(Exercise)
    if q:
        # SQLite: simple LIKE match
        stmt = stmt.where(Exercise.name.like(f"%{q}%"))
    if category:
        stmt = stmt.where(Exercise.category == category)
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
    # optional uniqueness check if name changes
    if "name" in data and data["name"] and data["name"] != ex.name:
        dup = session.exec(select(Exercise).where(Exercise.name == data["name"])).first()
        if dup:
            raise HTTPException(status_code=409, detail="Exercise with that name already exists")

    for k, v in data.items():
        setattr(ex, k, v)
    session.add(ex)
    session.commit()
    session.refresh(ex)
    return ex

@router.delete("/{exercise_id}", status_code=204)
def delete_exercise(exercise_id: int, session: Session = Depends(get_session)):
    ex = session.get(Exercise, exercise_id)
    if not ex:
        raise HTTPException(status_code=404, detail="Exercise not found")
    session.delete(ex)
    session.commit()
    return None
