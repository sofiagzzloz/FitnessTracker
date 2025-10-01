from datetime import date as dt_date
from typing import List, Optional
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, Query
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

def ensure_owner(obj, user_id: int, what: str = "resource"):
    if not obj or getattr(obj, "user_id", None) != user_id:
        raise HTTPException(status_code=404, detail=f"{what} not found")

# ---------- Templates ----------
@router.get("", response_model=List[WorkoutTemplateRead])
def list_templates(
    db: DBSession = Depends(get_session),
    q: Optional[str] = Query(None, description="Search by name (case-insensitive)"),
    user: User = Depends(get_current_user),
):
    stmt = select(WorkoutTemplate).where(WorkoutTemplate.user_id == user.id)
    if q:
        stmt = stmt.where(func.lower(WorkoutTemplate.name).like(f"%{q.lower()}%"))
    # newest first
    stmt = stmt.order_by(WorkoutTemplate.id.desc())
    return db.exec(stmt).all()

@router.post("", response_model=WorkoutTemplateRead, status_code=201)
def create_template(
    payload: WorkoutTemplateCreate,
    db: DBSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    name = (payload.name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="name is required")
    t = WorkoutTemplate(name=name, notes=(payload.notes or None), user_id=user.id)
    db.add(t)
    db.commit()
    db.refresh(t)
    return t

@router.get("/{template_id}", response_model=WorkoutTemplateRead)
def get_template(
    template_id: int,
    db: DBSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    t = db.get(WorkoutTemplate, template_id)
    ensure_owner(t, user.id, "template")
    return t

@router.delete("/{template_id}", status_code=204)
def delete_template(
    template_id: int,
    db: DBSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    t = db.get(WorkoutTemplate, template_id)
    ensure_owner(t, user.id, "template")
    items = db.exec(select(WorkoutItem).where(WorkoutItem.workout_template_id == template_id)).all()
    for it in items:
        db.delete(it)
    db.delete(t)
    db.commit()
    return None

# ---------- Template Items ----------
@router.get("/{template_id}/items", response_model=List[WorkoutItemRead])
def list_template_items(
    template_id: int,
    db: DBSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    t = db.get(WorkoutTemplate, template_id)
    ensure_owner(t, user.id, "template")

    stmt = (
        select(WorkoutItem)
        .where(WorkoutItem.workout_template_id == template_id)
        .order_by(WorkoutItem.order_index.asc(), WorkoutItem.id.asc())
    )
    return db.exec(stmt).all()

@router.post("/{template_id}/items", response_model=WorkoutItemRead, status_code=201)
def add_template_item(
    template_id: int,
    payload: WorkoutItemCreate,
    db: DBSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    t = db.get(WorkoutTemplate, template_id)
    ensure_owner(t, user.id, "template")

    ex = db.get(Exercise, payload.exercise_id)
    if not ex or ex.user_id != user.id:
        raise HTTPException(status_code=404, detail="exercise not found")

    # append to end
    cur_max = db.exec(
        select(func.max(WorkoutItem.order_index)).where(
            WorkoutItem.workout_template_id == template_id
        )
    ).first() or 0
    if isinstance(cur_max, tuple):  
        cur_max = cur_max[0] or 0
    next_order = (cur_max or 0) + 1

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
    db.add(it)
    db.commit()
    db.refresh(it)

    
    items = db.exec(
        select(WorkoutItem)
        .where(WorkoutItem.workout_template_id == template_id)
        .order_by(WorkoutItem.order_index.asc(), WorkoutItem.id.asc())
    ).all()
    for idx, obj in enumerate(items, start=1):
        if obj.order_index != idx:
            obj.order_index = idx
            db.add(obj)
    db.commit()
    return it

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
    it = db.get(WorkoutItem, item_id)
    if not it:
        raise HTTPException(status_code=404, detail="item not found")
    t = db.get(WorkoutTemplate, it.workout_template_id)
    ensure_owner(t, user.id, "template")

    data = payload.model_dump(exclude_unset=True)
    for field, value in data.items():
        setattr(it, field, value)

    db.add(it)
    db.commit()
    db.refresh(it)
    return it

@router.delete("/items/{item_id}", status_code=204)
def delete_template_item(
    item_id: int,
    db: DBSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    it = db.get(WorkoutItem, item_id)
    if not it:
        raise HTTPException(status_code=404, detail="item not found")
    t = db.get(WorkoutTemplate, it.workout_template_id)
    ensure_owner(t, user.id, "template")

    template_id = it.workout_template_id
    db.delete(it)
    db.commit()


    items = db.exec(
        select(WorkoutItem)
        .where(WorkoutItem.workout_template_id == template_id)
        .order_by(WorkoutItem.order_index.asc(), WorkoutItem.id.asc())
    ).all()
    for idx, obj in enumerate(items, start=1):
        if obj.order_index != idx:
            obj.order_index = idx
            db.add(obj)
    db.commit()
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
    if session_date > dt_date.today():
        raise HTTPException(status_code=422, detail="You can only log sessions for today or earlier.")
    t = db.get(WorkoutTemplate, template_id)
    ensure_owner(t, user.id, "template")

    ss = Session(
        user_id=user.id,
        date=session_date,
        title=title or t.name,
        notes=notes or None,
        workout_template_id=t.id,
    )
    db.add(ss)
    db.commit()
    db.refresh(ss)

    items = db.exec(
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
        db.add(si)
    db.commit()
    db.refresh(ss)
    return ss

# ---------- Muscle summary for a template ----------
@router.get("/{template_id}/muscles")
def get_template_muscles(
    template_id: int,
    db: DBSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    t = db.get(WorkoutTemplate, template_id)
    ensure_owner(t, user.id, "template")

    items = db.exec(
        select(WorkoutItem).where(WorkoutItem.workout_template_id == template_id)
    ).all()
    if not items:
        return {"template_id": template_id, "primary": {}, "secondary": {}}

    ex_ids = [it.exercise_id for it in items]
    links = db.exec(
        select(ExerciseMuscle, Muscle)
        .join(Muscle, ExerciseMuscle.muscle_id == Muscle.id)
        .where(ExerciseMuscle.exercise_id.in_(ex_ids))
    ).all()

    prim: dict[str, int] = {}
    sec: dict[str, int] = {}
    for link, m in links:
        if str(link.role) == "primary":
            prim[m.slug] = prim.get(m.slug, 0) + 1
        else:
            sec[m.slug] = sec.get(m.slug, 0) + 1

    return {"template_id": template_id, "primary": prim, "secondary": sec}

@router.post("/{template_id}/resequence", status_code=204)
def resequence_template(
    template_id: int,
    db: DBSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    t = db.get(WorkoutTemplate, template_id)
    ensure_owner(t, user.id, "template")

    items = db.exec(
        select(WorkoutItem)
        .where(WorkoutItem.workout_template_id == template_id)
        .order_by(WorkoutItem.id.asc())
    ).all()
    for idx, obj in enumerate(items, start=1):
        if obj.order_index != idx:
            obj.order_index = idx
            db.add(obj)
    db.commit()
    return None