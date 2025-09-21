from typing import List, Optional
from datetime import date as date_cls, datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select

from ..db import get_session
from ..models import WorkoutSession, WorkoutItem, Exercise
from ..schemas import SessionCreate, SessionRead, SessionItemCreate, SessionItemRead


router = APIRouter(prefix="/sessions", tags=["sessions"])

def _now() -> datetime:
    return datetime.utcnow()

def _exercise_or_400(session: Session, ex_id: int) -> Exercise:
    ex = session.get(Exercise, ex_id)
    if not ex:
        raise HTTPException(status_code=400, detail="Invalid exercise_id")
    return ex

@router.post("", response_model=SessionRead, status_code=201)
def create_session(payload: SessionCreate, session: Session = Depends(get_session)):
    s = WorkoutSession(**payload.model_dump())
    session.add(s)
    session.commit()
    session.refresh(s)
    return s

@router.get("", response_model=List[SessionRead])
def list_sessions(
    session: Session = Depends(get_session),
    on_date: Optional[str] = Query(None, description="YYYY-MM-DD"),
    start_date: Optional[str] = Query(None, description="YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="YYYY-MM-DD (inclusive)"),
):
    stmt = select(WorkoutSession)
    if on_date:
        d = date_cls.fromisoformat(on_date); stmt = stmt.where(WorkoutSession.date == d)
    if start_date:
        sd = date_cls.fromisoformat(start_date); stmt = stmt.where(WorkoutSession.date >= sd)
    if end_date:
        ed = date_cls.fromisoformat(end_date); stmt = stmt.where(WorkoutSession.date <= ed)
    stmt = stmt.order_by(WorkoutSession.date.desc(), WorkoutSession.id.desc())
    return session.exec(stmt).all()

@router.get("/{session_id}", response_model=SessionRead)
def get_session(session_id: int, session: Session = Depends(get_session)):
    s = session.get(WorkoutSession, session_id)
    if not s:
        raise HTTPException(status_code=404, detail="Session not found")
    return s

@router.post("/{session_id}/items", response_model=SessionItemRead, status_code=201)
def add_item(session_id: int, payload: SessionItemCreate, db: Session = Depends(get_session)):
    s = db.get(WorkoutSession, session_id)
    if not s:
        raise HTTPException(status_code=404, detail="Session not found")

    ex = _exercise_or_400(db, payload.exercise_id)

    it = WorkoutItem(
        session_id=session_id,
        exercise_id=payload.exercise_id,
        notes=payload.notes,
        order_index=payload.order_index,
        created_at=_now(),
        updated_at=_now(),
    )
    db.add(it)
    db.commit()
    db.refresh(it)

    return SessionItemRead(
        id=it.id,
        session_id=it.session_id,
        exercise_id=it.exercise_id,
        notes=it.notes,
        order_index=it.order_index,
        exercise_name=ex.name,
        exercise_category=ex.category,
    )

@router.delete("/{session_id}/items/{item_id}", status_code=204)
def delete_item(session_id: int, item_id: int, db: Session = Depends(get_session)):
    it = db.get(WorkoutItem, item_id)
    if not it or it.session_id != session_id:
        raise HTTPException(status_code=404, detail="Item not found")
    db.delete(it)
    db.commit()
    return