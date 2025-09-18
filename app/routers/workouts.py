from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select
from datetime import date as date_cls

from ..db import get_session
from ..models import Workout
from ..schemas import WorkoutCreate, WorkoutRead, WorkoutUpdate

router = APIRouter(prefix="/workouts", tags=["workouts"])

@router.post("", response_model=WorkoutRead, status_code=201)
def create_workout(payload: WorkoutCreate, session: Session = Depends(get_session)):
    for fld in ("sets", "reps", "weight_kg", "distance_km"):
        val = getattr(payload, fld)
        if val is not None and val < 0:
            raise HTTPException(status_code=400, detail=f"{fld} must be >= 0")

    w = Workout(**payload.model_dump())
    session.add(w)
    session.commit()
    session.refresh(w)
    return w

@router.get("", response_model=List[WorkoutRead])
def list_workouts(
    session: Session = Depends(get_session),
    exercise: Optional[str] = Query(None, description="Filter by exact exercise"),
    on_date: Optional[str] = Query(None, description="YYYY-MM-DD"),
    start_date: Optional[str] = Query(None, description="YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="YYYY-MM-DD (inclusive)"),
):
    stmt = select(Workout)

    if exercise:
        stmt = stmt.where(Workout.exercise == exercise)

    # single date
    if on_date:
        try:
            d = date_cls.fromisoformat(on_date)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid on_date (YYYY-MM-DD)")
        stmt = stmt.where(Workout.date == d)

    # date range
    if start_date:
        try:
            sd = date_cls.fromisoformat(start_date)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid start_date (YYYY-MM-DD)")
        stmt = stmt.where(Workout.date >= sd)
    if end_date:
        try:
            ed = date_cls.fromisoformat(end_date)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid end_date (YYYY-MM-DD)")
        stmt = stmt.where(Workout.date <= ed)

    return session.exec(stmt).all()

@router.get("/{workout_id}", response_model=WorkoutRead)
def get_workout(workout_id: int, session: Session = Depends(get_session)):
    w = session.get(Workout, workout_id)
    if not w:
        raise HTTPException(status_code=404, detail="Workout not found")
    return w


@router.put("/{workout_id}", response_model=WorkoutRead)
def update_workout(workout_id: int, payload: WorkoutUpdate, session: Session = Depends(get_session)):
    w = session.get(Workout, workout_id)
    if not w:
        raise HTTPException(status_code=404, detail="Workout not found")

    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(w, k, v)

    session.add(w)
    session.commit()
    session.refresh(w)
    return w

@router.delete("/{workout_id}", status_code=204)
def delete_workout(workout_id: int, session: Session = Depends(get_session)):
    w = session.get(Workout, workout_id)
    if not w:
        raise HTTPException(status_code=404, detail="Workout not found")
    session.delete(w)
    session.commit()
    return None

