from typing import List, Optional
import datetime as dt

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlmodel import Session as DBSession, select, delete

from ..db import get_session
from ..models import (
    Session,
    SessionItem,
    SessionSet,        # <-- make sure these exist in models.py
    SessionCardio,     # <-- make sure these exist in models.py
    Exercise,
    WorkoutItem,
)
from ..schemas import (
    SessionCreate,
    SessionRead,
    SessionItemCreate,
    SessionItemRead,
)

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


# ---------- helpers ----------
def _today() -> dt.date:
    return dt.date.today()

def _now() -> dt.datetime:
    return dt.datetime.utcnow()

def _exercise_or_400(db: DBSession, ex_id: int) -> Exercise:
    ex = db.get(Exercise, ex_id)
    if not ex:
        raise HTTPException(status_code=400, detail="Invalid exercise_id")
    return ex


# ---------- create session (optionally from a workout template) ----------
@router.post("", response_model=SessionRead, status_code=201)
def create_session(payload: SessionCreate, db: DBSession = Depends(get_session)):
    if payload.date > _today():
        raise HTTPException(status_code=422, detail="You can only log sessions for today or earlier.")

    s = Session(
        date=payload.date,
        title=(payload.title or None),
        notes=(payload.notes or None),
        workout_template_id=payload.workout_template_id,
        created_at=_now(),
        updated_at=_now(),
    )
    db.add(s)
    db.commit()
    db.refresh(s)

    tpl_id = payload.workout_template_id
    if tpl_id:
        # Try the common FK names gracefully
        fk_col = (
            getattr(WorkoutItem, "workout_id", None)
            or getattr(WorkoutItem, "workout_template_id", None)
            or getattr(WorkoutItem, "template_id", None)
        )
        if not fk_col:
            raise HTTPException(status_code=500, detail="WorkoutItem FK column not found")

        order_col = (
            getattr(WorkoutItem, "order_index", None)
            or getattr(WorkoutItem, "position", None)
            or getattr(WorkoutItem, "sort_order", None)
            or getattr(WorkoutItem, "id", None)
        )

        tpl_items = db.exec(
            select(WorkoutItem).where(fk_col == tpl_id).order_by(order_col.asc())
        ).all()

        next_order = 1
        for it in tpl_items:
            db.add(SessionItem(
                session_id=s.id,
                exercise_id=it.exercise_id,
                notes=None,
                order_index=next_order,
                created_at=_now(),
                updated_at=_now(),
            ))
            next_order += 1
        db.commit()

    return s


# ---------- list sessions ----------
@router.get("", response_model=List[SessionRead])
def list_sessions(
    on_date: Optional[str] = Query(None, description="YYYY-MM-DD"),
    start_date: Optional[str] = Query(None, description="YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="YYYY-MM-DD (inclusive)"),
    db: DBSession = Depends(get_session),
):
    stmt = select(Session)
    if on_date:
        d = dt.date.fromisoformat(on_date)
        stmt = stmt.where(Session.date == d)
    if start_date:
        sd = dt.date.fromisoformat(start_date)
        stmt = stmt.where(Session.date >= sd)
    if end_date:
        ed = dt.date.fromisoformat(end_date)
        stmt = stmt.where(Session.date <= ed)

    stmt = stmt.order_by(Session.date.desc(), Session.id.desc())
    return db.exec(stmt).all()


# ---------- read one ----------
@router.get("/{session_id}", response_model=SessionRead)
def read_session(session_id: int, db: DBSession = Depends(get_session)):
    s = db.get(Session, session_id)
    if not s:
        raise HTTPException(status_code=404, detail="Session not found")
    return s


# ---------- add item to a session ----------
@router.post("/{session_id}/items", response_model=SessionItemRead, status_code=201)
def add_item(session_id: int, payload: SessionItemCreate, db: DBSession = Depends(get_session)):
    s = db.get(Session, session_id)
    if not s:
        raise HTTPException(status_code=404, detail="Session not found")
    if s.date > _today():
        raise HTTPException(status_code=422, detail="This session is future-dated and cannot be modified.")

    ex = _exercise_or_400(db, payload.exercise_id)

    if payload.order_index is None:
        max_orders = db.exec(
            select(SessionItem.order_index).where(SessionItem.session_id == session_id)
        ).all()
        next_order = (max([o for o in max_orders if o is not None], default=0) + 1) if max_orders else 1
    else:
        next_order = payload.order_index

    it = SessionItem(
        session_id=session_id,
        exercise_id=payload.exercise_id,
        notes=(payload.notes or None),
        order_index=next_order,
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


# ---------- list items (table on the right) ----------
@router.get("/{session_id}/items", response_model=List[SessionItemRead])
def list_items(session_id: int, db: DBSession = Depends(get_session)):
    s = db.get(Session, session_id)
    if not s:
        raise HTTPException(status_code=404, detail="Session not found")

    rows = db.exec(
        select(SessionItem).where(SessionItem.session_id == session_id).order_by(SessionItem.order_index.asc())
    ).all()

    ex_ids = {r.exercise_id for r in rows}
    ex_map = {e.id: e for e in db.exec(select(Exercise).where(Exercise.id.in_(ex_ids))).all()} if ex_ids else {}

    return [
        SessionItemRead(
            id=r.id,
            session_id=r.session_id,
            exercise_id=r.exercise_id,
            notes=r.notes,
            order_index=r.order_index,
            exercise_name=(ex_map.get(r.exercise_id).name if ex_map.get(r.exercise_id) else ""),
            exercise_category=(ex_map.get(r.exercise_id).category if ex_map.get(r.exercise_id) else None),
        )
        for r in rows
    ]


# ---------- update item (notes / order) ----------
class SessionItemUpdate(BaseModel):
    notes: Optional[str] = None
    order_index: Optional[int] = None

@router.patch("/{session_id}/items/{item_id}", response_model=SessionItemRead)
def update_item(session_id: int, item_id: int, payload: SessionItemUpdate, db: DBSession = Depends(get_session)):
    it = db.get(SessionItem, item_id)
    if not it or it.session_id != session_id:
        raise HTTPException(status_code=404, detail="Item not found")

    s = db.get(Session, session_id)
    if s.date > _today():
        raise HTTPException(status_code=422, detail="This session is future-dated and cannot be modified.")

    if payload.notes is not None:
        it.notes = (payload.notes or None)
    if payload.order_index is not None:
        it.order_index = payload.order_index

    it.updated_at = _now()
    db.add(it)
    db.commit()
    db.refresh(it)

    ex = db.get(Exercise, it.exercise_id)
    return SessionItemRead(
        id=it.id,
        session_id=it.session_id,
        exercise_id=it.exercise_id,
        notes=it.notes,
        order_index=it.order_index,
        exercise_name=(ex.name if ex else ""),
        exercise_category=(ex.category if ex else None),
    )


# ---------- delete item (and its child rows) ----------
@router.delete("/{session_id}/items/{item_id}", status_code=204)
def delete_item(session_id: int, item_id: int, db: DBSession = Depends(get_session)):
    it = db.get(SessionItem, item_id)
    if not it or it.session_id != session_id:
        raise HTTPException(status_code=404, detail="Item not found")

    # delete children first if they exist
    db.exec(delete(SessionSet).where(SessionSet.session_item_id == item_id))
    db.exec(delete(SessionCardio).where(SessionCardio.session_item_id == item_id))

    db.delete(it)
    db.commit()
    return None


# ---------- delete session (and ALL its children) ----------
@router.delete("/{session_id}", status_code=204)
def delete_session(session_id: int, db: DBSession = Depends(get_session)):
    s = db.get(Session, session_id)
    if not s:
        raise HTTPException(status_code=404, detail="Session not found")

    # 1) collect child item ids (this returns ints, not objects)
    item_ids = db.exec(
        select(SessionItem.id).where(SessionItem.session_id == session_id)
    ).all()

    # 2) delete child rows first (safer than relying on ON DELETE CASCADE)
    if item_ids:
        db.exec(delete(SessionItem).where(SessionItem.id.in_(item_ids)))

        # If you still have SessionSet / SessionCardio tables in your DB, also:
        # db.exec(delete(SessionSet).where(SessionSet.session_item_id.in_(item_ids)))
        # db.exec(delete(SessionCardio).where(SessionCardio.session_item_id.in_(item_ids)))

    # 3) delete the parent session
    db.exec(delete(Session).where(Session.id == session_id))
    db.commit()
    return None