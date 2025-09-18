from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select
from datetime import date as date_cls
from collections import defaultdict

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

    # basic non-negative checks
    for fld in ("sets", "reps", "weight_kg", "distance_km"):
        val = getattr(payload, fld)
        if val is not None and val < 0:
            raise HTTPException(status_code=400, detail=f"{fld} must be >= 0")

    w = Workout(**payload.model_dump())
    session.add(w)
    session.commit()
    session.refresh(w)

    # return enriched response
    return WorkoutRead(
        **w.model_dump(),
        exercise_name=ex.name,
        exercise_category=ex.category,
    )

@router.get("", response_model=List[WorkoutRead])
def list_workouts(
    session: Session = Depends(get_session),
    exercise: Optional[str] = Query(None, description="Exact exercise name"),
    category: Optional[str] = Query(None, description="Exercise category"),
    on_date: Optional[str] = Query(None, description="YYYY-MM-DD"),
    start_date: Optional[str] = Query(None, description="YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="YYYY-MM-DD (inclusive)"),
):
    stmt = select(Workout)
    from datetime import date as date_cls
    if on_date:
        d = date_cls.fromisoformat(on_date); stmt = stmt.where(Workout.date == d)
    if start_date:
        sd = date_cls.fromisoformat(start_date); stmt = stmt.where(Workout.date >= sd)
    if end_date:
        ed = date_cls.fromisoformat(end_date); stmt = stmt.where(Workout.date <= ed)

    items = session.exec(stmt).all()
    out = []
    for w in items:
        ex = session.get(Exercise, w.exercise_id)
        if exercise and (not ex or ex.name != exercise):
            continue
        if category and (not ex or ex.category != category):
            continue
        out.append(
            WorkoutRead(
                **w.model_dump(),
                exercise_name=ex.name if ex else "",
                exercise_category=ex.category if ex else None,
            )
        )
    return out


@router.get("/{workout_id}", response_model=WorkoutRead)
def get_workout(workout_id: int, session: Session = Depends(get_session)):
    w = session.get(Workout, workout_id)
    if not w:
        raise HTTPException(status_code=404, detail="Workout not found")
    ex = session.get(Exercise, w.exercise_id)
    return WorkoutRead(
        **w.model_dump(),
        exercise_name=ex.name,
        exercise_category=ex.category,
    )

@router.put("/{workout_id}", response_model=WorkoutRead)
def update_workout(workout_id: int, payload: WorkoutUpdate, session: Session = Depends(get_session)):
    w = session.get(Workout, workout_id)
    if not w:
        raise HTTPException(status_code=404, detail="Workout not found")

    data = payload.model_dump(exclude_unset=True)

    # Validate non-negative fields if provided
    for fld in ("sets", "reps", "weight_kg", "distance_km"):
        if fld in data and data[fld] is not None and data[fld] < 0:
            raise HTTPException(status_code=400, detail=f"{fld} must be >= 0")

    # If exercise_id changes, validate it exists
    if "exercise_id" in data and data["exercise_id"] is not None:
        ex_new = session.get(Exercise, data["exercise_id"])
        if not ex_new:
            raise HTTPException(status_code=400, detail="Invalid exercise_id")

    
    for k, v in data.items():
        setattr(w, k, v)

    session.add(w)
    session.commit()
    session.refresh(w)

    
    ex = session.get(Exercise, w.exercise_id)
    return WorkoutRead(
        **w.model_dump(),
        exercise_name=ex.name,
        exercise_category=ex.category,
    )

@router.delete("/{workout_id}", status_code=204)
def delete_workout(workout_id: int, session: Session = Depends(get_session)):
    w = session.get(Workout, workout_id)
    if not w:
        raise HTTPException(status_code=404, detail="Workout not found")
    session.delete(w)
    session.commit()
    return None

# first i need to do the updates so this will be for later!!
@router.get("/stats")
def workout_stats(session: Session = Depends(get_session)):
    workouts = session.exec(select(Workout)).all()
    by_ex = defaultdict(lambda: {"count": 0, "total_volume": 0.0, "total_distance_km": 0.0})

    for w in workouts:
        ex = session.get(Exercise, w.exercise_id)
        key = ex.name if ex else f"id:{w.exercise_id}"
        by_ex[key]["count"] += 1
        # volume = sets * reps * weight_kg (if provided)
        if w.sets and w.reps and w.weight_kg:
            by_ex[key]["total_volume"] += float(w.sets * w.reps * w.weight_kg)
        if w.distance_km:
            by_ex[key]["total_distance_km"] += float(w.distance_km)

    return {
        "total_workouts": len(workouts),
        "by_exercise": [
            {"exercise": k, **v} for k, v in sorted(by_ex.items())
        ],
    }

