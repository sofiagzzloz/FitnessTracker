from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select
from datetime import date as date_cls

from ..db import get_session
from ..models import Workout, Exercise
from ..schemas import WorkoutCreate, WorkoutRead, WorkoutUpdate

router = APIRouter(prefix="/workouts", tags=["workouts"])

@router.post("", response_model=WorkoutRead, status_code=201)
def create_workout(payload: WorkoutCreate, session: Session = Depends(get_session)):
    # validate exercise exists
    ex = session.get(Exercise, payload.exercise_id)
    if not ex:
        raise HTTPException(status_code=400, detail="Invalid exercise_id")

    # non-negative checks
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
def list_workouts(session: Session = Depends(get_session)):
    workouts = session.exec(select(Workout)).all()
    result = []
    for w in workouts:
        ex = session.get(Exercise, w.exercise_id)
        result.append(
            WorkoutRead(
                **w.__dict__,
                exercise_name=ex.name,
                exercise_category=ex.category
            )
        )
    return result


@router.get("/{workout_id}", response_model=WorkoutRead)
def get_workout(workout_id: int, session: Session = Depends(get_session)):
    w = session.get(Workout, workout_id)
    if not w:
        raise HTTPException(status_code=404, detail="Workout not found")
    ex = session.get(Exercise, w.exercise_id)
    return WorkoutRead(
        **w.__dict__,
        exercise_name=ex.name,
        exercise_category=ex.category
    )

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

