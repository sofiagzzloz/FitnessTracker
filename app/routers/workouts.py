# app/routers/workouts.py
from datetime import date as dt_date
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func
from sqlmodel import Session as DBSession, select

from ..db import get_session
from ..auth import get_current_user
from ..models import (
    WorkoutTemplate, WorkoutItem, Exercise,
    Session, SessionItem, Muscle, ExerciseMuscle, User
)
from ..schemas import (
    WorkoutTemplateCreate, WorkoutTemplateRead,
    WorkoutItemCreate, WorkoutItemRead,
    SessionRead
)

router = APIRouter(prefix="/api/workouts", tags=["workouts"])

# ---------- helpers ----------
def ensure_owner(obj, user_id: int, what: str = "resource"):
    """
    Enforce per-user ownership *only if* the model has a user_id column.
    Always 404 on missing/foreign objects to avoid leakage.
    """
    if not obj:
        raise HTTPException(status_code=404, detail=f"{what} not found")
    if hasattr(obj, "user_id") and getattr(obj, "user_id") != user_id:
        raise HTTPException(status_code=404, detail=f"{what} not found")

def stmt_with_owner(stmt, model, user_id: int):
    """
    If model has a user_id column, add WHERE user_id = :user_id
    """
    if hasattr(model, "user_id"):
        return stmt.where(getattr(model, "user_id") == user_id)
    return stmt

# ---------- partial update schema for items ----------
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

# ---------- Templates ----------
@router.get("", response_model=List[WorkoutTemplateRead])
def list_templates(
    session: DBSession = Depends(get_session),
    q: Optional[str] = Query(None, description="Search by name (case-insensitive)"),
    user: User = Depends(get_current_user),
):
    stmt = select(WorkoutTemplate)
    stmt = stmt_with_owner(stmt, WorkoutTemplate, user.id)
    if q:
        stmt = stmt.where(func.lower(WorkoutTemplate.name).like(f"%{q.lower()}%"))
    stmt = stmt.order_by(WorkoutTemplate.created_at.desc(), WorkoutTemplate.id.desc())
    return session.exec(stmt).all()

@router.post("", response_model=WorkoutTemplateRead, status_code=201)
def create_template(
    payload: WorkoutTemplateCreate,
    session: DBSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    name = (payload.name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="name is required")

    kwargs = dict(name=name, notes=(payload.notes or None))
    if hasattr(WorkoutTemplate, "user_id"):
        kwargs["user_id"] = user.id

    t = WorkoutTemplate(**kwargs)
    session.add(t)
    session.commit()
    session.refresh(t)
    return t

@router.get("/{template_id}", response_model=WorkoutTemplateRead)
def get_template(
    template_id: int,
    session: DBSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    t = session.get(WorkoutTemplate, template_id)
    ensure_owner(t, user.id, "template")
    return t

@router.delete("/{template_id}", status_code=204)
def delete_template(
    template_id: int,
    session: DBSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    t = session.get(WorkoutTemplate, template_id)
    ensure_owner(t, user.id, "template")

    items = session.exec(
        select(WorkoutItem).where(WorkoutItem.workout_template_id == template_id)
    ).all()
    for it in items:
        session.delete(it)

    session.delete(t)
    session.commit()
    return None

# ---------- Template Items ----------
@router.get("/{template_id}/items", response_model=List[WorkoutItemRead])
def list_template_items(
    template_id: int,
    session: DBSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    t = session.get(WorkoutTemplate, template_id)
    ensure_owner(t, user.id, "template")

    stmt = (
        select(WorkoutItem)
        .where(WorkoutItem.workout_template_id == template_id)
        .order_by(WorkoutItem.order_index.asc(), WorkoutItem.id.asc())
    )
    return session.exec(stmt).all()

@router.post("/{template_id}/items", response_model=WorkoutItemRead, status_code=201)
def add_template_item(
    template_id: int,
    payload: WorkoutItemCreate,
    session: DBSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    # verify template ownership
    t = session.get(WorkoutTemplate, template_id)
    ensure_owner(t, user.id, "template")

    # verify exercise ownership (if exercises are scoped)
    ex = session.get(Exercise, payload.exercise_id)
    if not ex:
        raise HTTPException(status_code=404, detail="exercise not found")
    if hasattr(Exercise, "user_id") and ex.user_id != user.id:
        raise HTTPException(status_code=404, detail="exercise not found")

    # robust "append to end"
    cur_max = (
        session.exec(
            select(func.max(WorkoutItem.order_index)).where(
                WorkoutItem.workout_template_id == template_id
            )
        ).first()
        or 0
    )
    if isinstance(cur_max, tuple):  # safety for some SQL backends
        cur_max = cur_max[0] or 0
    next_order = int(cur_max) + 1

    it = WorkoutItem(
        workout_template_id=template_id,
        exercise_id=payload.exercise_id,
        order_index=next_order,
        planned_sets=payload.planned_sets,
        planned_reps=payload.planned_reps,
        planned_weight=payload.planned_weight,
        planned_rpe=payload.planned_rpe,
        planned_minutes=payload.planned_minutes,
        planned_distance=payload.planned_distance,
        planned_distance_unit=payload.planned_distance_unit,
        notes=(payload.notes or None),
    )
    session.add(it)
    session.commit()
    session.refresh(it)

    # optional resequence to ensure contiguous 1..n
    items = session.exec(
        select(WorkoutItem)
        .where(WorkoutItem.workout_template_id == template_id)
        .order_by(WorkoutItem.order_index.asc(), WorkoutItem.id.asc())
    ).all()
    for idx, obj in enumerate(items, start=1):
        if obj.order_index != idx:
            obj.order_index = idx
            session.add(obj)
    session.commit()

    return it

@router.patch("/items/{item_id}", response_model=WorkoutItemRead)
def update_template_item(
    item_id: int,
    payload: WorkoutItemUpdate,
    session: DBSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    it = session.get(WorkoutItem, item_id)
    if not it:
        raise HTTPException(status_code=404, detail="item not found")

    # check parent ownership
    t = session.get(WorkoutTemplate, it.workout_template_id)
    ensure_owner(t, user.id, "template")

    data = payload.model_dump(exclude_unset=True)
    for field, value in data.items():
        setattr(it, field, value)

    session.add(it)
    session.commit()
    session.refresh(it)
    return it

@router.delete("/items/{item_id}", status_code=204)
def delete_template_item(
    item_id: int,
    session: DBSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    it = session.get(WorkoutItem, item_id)
    if not it:
        raise HTTPException(status_code=404, detail="item not found")

    t = session.get(WorkoutTemplate, it.workout_template_id)
    ensure_owner(t, user.id, "template")

    template_id = it.workout_template_id
    session.delete(it)
    session.commit()

    # resequence after delete
    items = session.exec(
        select(WorkoutItem)
        .where(WorkoutItem.workout_template_id == template_id)
        .order_by(WorkoutItem.order_index.asc(), WorkoutItem.id.asc())
    ).all()
    for idx, obj in enumerate(items, start=1):
        if obj.order_index != idx:
            obj.order_index = idx
            session.add(obj)
    session.commit()
    return None

# ---------- Make Session from Template (date <= today) ----------
@router.post("/{template_id}/make-session", response_model=SessionRead, status_code=201)
def make_session_from_template(
    template_id: int,
    session_date: dt_date,
    title: Optional[str] = None,
    notes: Optional[str] = None,
    session: DBSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    if session_date > dt_date.today():
        raise HTTPException(status_code=422, detail="You can only log sessions for today or earlier.")

    t = session.get(WorkoutTemplate, template_id)
    ensure_owner(t, user.id, "template")

    ss_kwargs = dict(
        date=session_date,
        title=title or t.name,
        notes=notes or None,
        workout_template_id=t.id,
    )
    # add user_id if the column exists
    if hasattr(Session, "user_id"):
        ss_kwargs["user_id"] = user.id

    ss = Session(**ss_kwargs)
    session.add(ss)
    session.commit()
    session.refresh(ss)

    items = session.exec(
        select(WorkoutItem)
        .where(WorkoutItem.workout_template_id == template_id)
        .order_by(WorkoutItem.order_index.asc(), WorkoutItem.id.asc())
    ).all()
    for idx, src in enumerate(items, start=1):
        si = SessionItem(
            session_id=ss.id,
            order_index=idx,
            exercise_id=src.exercise_id,
            notes=src.notes,
        )
        session.add(si)
    session.commit()
    session.refresh(ss)
    return ss

# ---------- Muscle summary for a template ----------
@router.get("/{template_id}/muscles")
def get_template_muscles(
    template_id: int,
    session: DBSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    t = session.get(WorkoutTemplate, template_id)
    ensure_owner(t, user.id, "template")

    items = session.exec(
        select(WorkoutItem).where(WorkoutItem.workout_template_id == template_id)
    ).all()
    if not items:
        return {"template_id": template_id, "primary": {}, "secondary": {}}

    ex_ids = [it.exercise_id for it in items]
    links = session.exec(
        select(ExerciseMuscle, Muscle)
        .join(Muscle, ExerciseMuscle.muscle_id == Muscle.id)
        .where(ExerciseMuscle.exercise_id.in_(ex_ids))
    ).all()

    prim: dict[str, int] = {}
    sec: dict[str, int] = {}
    for link, m in links:
        # link.role is an Enum; support both Enum and str
        role_val = str(getattr(link, "role", "") or "")
        if role_val == "primary":
            prim[m.slug] = prim.get(m.slug, 0) + 1
        else:
            sec[m.slug] = sec.get(m.slug, 0) + 1

    return {"template_id": template_id, "primary": prim, "secondary": sec}

# ---------- Resequence (by creation order) ----------
@router.post("/{template_id}/resequence", status_code=204)
def resequence_template(
    template_id: int,
    session: DBSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    t = session.get(WorkoutTemplate, template_id)
    ensure_owner(t, user.id, "template")

    items = session.exec(
        select(WorkoutItem)
        .where(WorkoutItem.workout_template_id == template_id)
        .order_by(WorkoutItem.id.asc())
    ).all()
    for idx, obj in enumerate(items, start=1):
        if obj.order_index != idx:
            obj.order_index = idx
            session.add(obj)
    session.commit()
    return None