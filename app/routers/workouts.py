from datetime import date as dt_date
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlmodel import Session as DBSession


from ..db import get_session
from ..auth import get_current_user
from ..models import User
from ..schemas import (
    WorkoutTemplateCreate,
    WorkoutTemplateRead,
    WorkoutItemCreate,
    WorkoutItemRead,
    SessionRead,
)
from ..services import workouts_service as svc


router = APIRouter(prefix="/api/workouts", tags=["workouts"])


# ---------- Templates ----------
@router.get("", response_model=List[WorkoutTemplateRead])
def list_templates(
    db: DBSession = Depends(get_session),
    q: Optional[str] = Query(None, description="Search by name (case-insensitive)"),
    user: User = Depends(get_current_user),
):
    return svc.list_templates(db=db, user_id=user.id, q=q)


@router.post("", response_model=WorkoutTemplateRead, status_code=201)
def create_template(
    payload: WorkoutTemplateCreate,
    db: DBSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    return svc.create_template(db=db, user_id=user.id, payload=payload)


@router.get("/{template_id}", response_model=WorkoutTemplateRead)
def get_template(
    template_id: int,
    db: DBSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    return svc.get_template(db=db, user_id=user.id, template_id=template_id)


@router.delete("/{template_id}", status_code=204)
def delete_template(
    template_id: int,
    db: DBSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    svc.delete_template(db=db, user_id=user.id, template_id=template_id)
    return None


# ---------- Template Items ----------
@router.get("/{template_id}/items", response_model=List[WorkoutItemRead])
def list_template_items(
    template_id: int,
    db: DBSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    return svc.list_template_items(db=db, user_id=user.id, template_id=template_id)


@router.post("/{template_id}/items", response_model=WorkoutItemRead, status_code=201)
def add_template_item(
    template_id: int,
    payload: WorkoutItemCreate,
    db: DBSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    return svc.add_template_item(
        db=db, user_id=user.id, template_id=template_id, payload=payload
    )


class WorkoutItemUpdate(BaseModel):
    planned_sets: Optional[int] = None
    planned_reps: Optional[int] = None
    planned_weight: Optional[float] = None
    planned_rpe: Optional[float] = None
    planned_minutes: Optional[int] = None
    planned_distance: Optional[float] = None
    planned_distance_unit: Optional[str] = None
    notes: Optional[str] = None
    order_index: Optional[int] = None


@router.patch("/items/{item_id}", response_model=WorkoutItemRead)
def update_template_item(
    item_id: int,
    payload: WorkoutItemUpdate,
    db: DBSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    return svc.update_template_item(
        db=db, user_id=user.id, item_id=item_id, payload=payload
    )


@router.delete("/items/{item_id}", status_code=204)
def delete_template_item(
    item_id: int,
    db: DBSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    svc.delete_template_item(db=db, user_id=user.id, item_id=item_id)
    return None


# ---------- Make Session from Template ----------
@router.post("/{template_id}/make-session", response_model=SessionRead, status_code=201)
def make_session_from_template(
    template_id: int,
    session_date: dt_date,
    title: Optional[str] = None,
    notes: Optional[str] = None,
    db: DBSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    return svc.make_session_from_template(
        db=db,
        user_id=user.id,
        template_id=template_id,
        session_date=session_date,
        title=title,
        notes=notes,
    )


# ---------- Muscle summary for a template ----------
@router.get("/{template_id}/muscles")
def get_template_muscles(
    template_id: int,
    db: DBSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    return svc.template_muscles(db=db, user_id=user.id, template_id=template_id)


@router.post("/{template_id}/resequence", status_code=204)
def resequence_template(
    template_id: int,
    db: DBSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    svc.resequence_template(db=db, user_id=user.id, template_id=template_id)
    return None
