from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlmodel import Session as DBSession


from ..db import get_session
from ..auth import get_current_user
from ..models import Category, User


from ..schemas import ExerciseCreate, ExerciseRead, ExerciseUpdate
from ..services import exercises_service as svc


router = APIRouter(prefix="/api/exercises", tags=["exercises"])


@router.post("", response_model=ExerciseRead, status_code=201)
def create_exercise(
    payload: ExerciseCreate,
    db: DBSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    return svc.create_exercise(db=db, user_id=user.id, payload=payload)


@router.get("", response_model=List[ExerciseRead])
def list_exercises(
    db: DBSession = Depends(get_session),
    user: User = Depends(get_current_user),
    q: Optional[str] = Query(
        None, description="Substring name match (case-insensitive)"
    ),
    category: Optional[Category] = Query(None, description="Category filter"),
    limit: int = Query(100, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    return svc.list_exercises(
        db=db, user_id=user.id, q=q, category=category, limit=limit, offset=offset
    )


@router.get("/{exercise_id}", response_model=ExerciseRead)
def get_exercise(
    exercise_id: int,
    db: DBSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    return svc.get_exercise(db=db, user_id=user.id, exercise_id=exercise_id)


@router.put("/{exercise_id}", response_model=ExerciseRead)
def update_exercise(
    exercise_id: int,
    payload: ExerciseUpdate,
    db: DBSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    return svc.update_exercise(
        db=db, user_id=user.id, exercise_id=exercise_id, payload=payload
    )


@router.delete("/{exercise_id}", status_code=204)
def delete_exercise(
    exercise_id: int,
    db: DBSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    svc.delete_exercise(db=db, user_id=user.id, exercise_id=exercise_id)
    return None


@router.get("/{exercise_id}/usage")
def get_exercise_usage(
    exercise_id: int,
    db: DBSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    return svc.get_exercise_usage(db=db, user_id=user.id, exercise_id=exercise_id)
