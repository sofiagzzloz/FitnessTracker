from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session as SqlSession, select
from datetime import date as date_cls

from ..db import get_session as get_db
from ..models import WorkoutTemplate, WorkoutTemplateItem, Exercise, WorkoutSession, WorkoutItem
from ..schemas import (
    TemplateCreate, TemplateRead,
    TemplateItemCreate, TemplateItemRead,
)

router = APIRouter(prefix="/templates", tags=["templates"])

def _get_template_or_404(db: SqlSession, tid: int) -> WorkoutTemplate:
    t = db.get(WorkoutTemplate, tid)
    if not t:
        raise HTTPException(status_code=404, detail="Template not found")
    return t

def _exercise_or_400(db: SqlSession, ex_id: int) -> Exercise:
    ex = db.get(Exercise, ex_id)
    if not ex:
        raise HTTPException(status_code=400, detail="Invalid exercise_id")
    return ex

@router.post("", response_model=TemplateRead, status_code=201)
def create_template(payload: TemplateCreate, db: SqlSession = Depends(get_db)):
    t = WorkoutTemplate(**payload.model_dump())
    db.add(t); db.commit(); db.refresh(t)
    return t

@router.get("", response_model=List[TemplateRead])
def list_templates(db: SqlSession = Depends(get_db)):
    stmt = select(WorkoutTemplate).order_by(WorkoutTemplate.id.desc())
    return db.exec(stmt).all()

@router.delete("/{template_id}", status_code=204)
def delete_template(template_id: int, db: SqlSession = Depends(get_db)):
    t = _get_template_or_404(db, template_id)
    items = db.exec(select(WorkoutTemplateItem).where(WorkoutTemplateItem.template_id == template_id)).all()
    for it in items:
        db.delete(it)
    db.delete(t)
    db.commit()
    return

@router.post("/{template_id}/items", response_model=TemplateItemRead, status_code=201)
def add_item(template_id: int, payload: TemplateItemCreate, db: SqlSession = Depends(get_db)):
    _get_template_or_404(db, template_id)
    ex = _exercise_or_400(db, payload.exercise_id)
    it = WorkoutTemplateItem(template_id=template_id, **payload.model_dump())
    db.add(it); db.commit(); db.refresh(it)
    return TemplateItemRead(
        id=it.id, template_id=it.template_id, exercise_id=it.exercise_id,
        sets=it.sets, reps=it.reps, weight_kg=it.weight_kg, distance_km=it.distance_km,
        notes=it.notes, order_index=it.order_index,
        exercise_name=ex.name, exercise_category=ex.category,
    )

@router.get("/{template_id}/items", response_model=List[TemplateItemRead])
def list_items(template_id: int, db: SqlSession = Depends(get_db)):
    _get_template_or_404(db, template_id)
    rows = db.exec(select(WorkoutTemplateItem).where(WorkoutTemplateItem.template_id == template_id)).all()
    ex_ids = {r.exercise_id for r in rows}
    ex_map = {e.id: e for e in db.exec(select(Exercise).where(Exercise.id.in_(ex_ids))).all()}
    out: List[TemplateItemRead] = []
    for r in rows:
        ex = ex_map.get(r.exercise_id)
        out.append(TemplateItemRead(
            id=r.id, template_id=r.template_id, exercise_id=r.exercise_id,
            sets=r.sets, reps=r.reps, weight_kg=r.weight_kg, distance_km=r.distance_km,
            notes=r.notes, order_index=r.order_index,
            exercise_name=ex.name if ex else "", exercise_category=ex.category if ex else None
        ))
    return out

@router.delete("/{template_id}/items/{item_id}", status_code=204)
def delete_item(template_id: int, item_id: int, db: SqlSession = Depends(get_db)):
    it = db.get(WorkoutTemplateItem, item_id)
    if not it or it.template_id != template_id:
        raise HTTPException(status_code=404, detail="Item not found")
    db.delete(it); db.commit()
    return


@router.post("/{template_id}/make-session", status_code=201)
def make_session_from_template(
    template_id: int,
    date: str,                       
    title: str | None = None,
    notes: str | None = None,
    db: SqlSession = Depends(get_db),
):
    t = _get_template_or_404(db, template_id)
    try:
        d = date_cls.fromisoformat(date)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid date format, use YYYY-MM-DD")

    # create session
    s = WorkoutSession(date=d, title=title or t.name, notes=notes or t.notes)
    db.add(s); db.commit(); db.refresh(s)

    # copy items as session items (planned fields can be copied to notes)
    rows = db.exec(select(WorkoutTemplateItem).where(WorkoutTemplateItem.template_id == template_id)).all()
    for r in rows:
        db.add(WorkoutItem(
            session_id=s.id,
            exercise_id=r.exercise_id,
            notes=r.notes,               
            order_index=r.order_index,
        ))
    db.commit()
    return {"session_id": s.id}