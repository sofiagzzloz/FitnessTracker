from __future__ import annotations
from typing import List, Optional
import datetime as dt
from fastapi import HTTPException
from sqlmodel import Session as DBSession, select, delete


from ..models import (
   Session,
   SessionItem,
   SessionSet,
   SessionCardio,
   Exercise,
   WorkoutItem,
)
from ..schemas import (
   SessionCreate,
   SessionRead,
   SessionItemCreate,
   SessionItemRead,
)
from .common import ensure_owner, today, now_utc




def _exercise_or_400(db: DBSession, ex_id: int, user_id: int) -> Exercise:
   ex = db.get(Exercise, ex_id)
   if not ex or ex.user_id != user_id:
       raise HTTPException(status_code=400, detail="Invalid exercise_id")
   return ex




def create_session(db: DBSession, user_id: int, payload: SessionCreate) -> Session:
   if payload.date > today():
       raise HTTPException(status_code=422, detail="You can only log sessions for today or earlier.")


   s = Session(
       user_id=user_id,
       date=payload.date,
       title=(payload.title or None),
       notes=(payload.notes or None),
       workout_template_id=payload.workout_template_id,
       created_at=now_utc(),
       updated_at=now_utc(),
   )
   db.add(s)
   db.commit()
   db.refresh(s)


   tpl_id = payload.workout_template_id
   if tpl_id:
       fk_col = getattr(WorkoutItem, "workout_template_id")
       order_col = getattr(WorkoutItem, "order_index", getattr(WorkoutItem, "id"))


       tpl_items = db.exec(
           select(WorkoutItem)
           .where(fk_col == tpl_id)
           .order_by(order_col.asc())
       ).all()


       for idx, it in enumerate(tpl_items, start=1):
           db.add(SessionItem(
               session_id=s.id,
               exercise_id=it.exercise_id,
               notes=None,
               order_index=idx,
               created_at=now_utc(),
               updated_at=now_utc(),
           ))
       db.commit()


   return s




def list_sessions(
   db: DBSession,
   user_id: int,
   on_date: Optional[str],
   start_date: Optional[str],
   end_date: Optional[str],
) -> List[Session]:
   stmt = select(Session).where(Session.user_id == user_id)
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




def read_session(db: DBSession, user_id: int, session_id: int) -> Session:
   s = db.get(Session, session_id)
   ensure_owner(s, user_id, "session")
   return s  # type: ignore




def add_item(db: DBSession, user_id: int, session_id: int, payload: SessionItemCreate) -> SessionItemRead:
   s = db.get(Session, session_id)
   ensure_owner(s, user_id, "session")
   assert s is not None
   if s.date > today():
       raise HTTPException(status_code=422, detail="This session is future-dated and cannot be modified.")
   ex = _exercise_or_400(db, payload.exercise_id, user_id)


   max_orders = db.exec(select(SessionItem.order_index).where(SessionItem.session_id == session_id)).all()
   next_order = (max([o for o in max_orders if o is not None], default=0) + 1) if max_orders else 1


   it = SessionItem(
       session_id=session_id,
       exercise_id=payload.exercise_id,
       notes=(payload.notes or None),
       order_index=next_order,
       created_at=now_utc(),
       updated_at=now_utc(),
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




def list_items(db: DBSession, user_id: int, session_id: int) -> List[SessionItemRead]:
   s = db.get(Session, session_id)
   ensure_owner(s, user_id, "session")


   rows = db.exec(select(SessionItem).where(SessionItem.session_id == session_id).order_by(SessionItem.order_index.asc())).all()
   ex_ids = {r.exercise_id for r in rows}
   ex_map = {e.id: e for e in db.exec(select(Exercise).where(Exercise.id.in_(ex_ids)).where(Exercise.user_id == user_id)).all()} if ex_ids else {}


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




def update_item(db: DBSession, user_id: int, session_id: int, item_id: int, notes: Optional[str], order_index: Optional[int]) -> SessionItemRead:
   it = db.get(SessionItem, item_id)
   if not it or it.session_id != session_id:
       raise HTTPException(status_code=404, detail="Item not found")
   s = db.get(Session, session_id)
   ensure_owner(s, user_id, "session")
   assert s is not None
   if s.date > today():
       raise HTTPException(status_code=422, detail="This session is future-dated and cannot be modified.")
   if notes is not None:
       it.notes = (notes or None)
   if order_index is not None:
       it.order_index = order_index
   it.updated_at = now_utc()
   db.add(it)
   db.commit()
   db.refresh(it)
   ex = db.get(Exercise, it.exercise_id)
   if ex and ex.user_id != user_id:
       ex = None
   return SessionItemRead(
       id=it.id,
       session_id=it.session_id,
       exercise_id=it.exercise_id,
       notes=it.notes,
       order_index=it.order_index,
       exercise_name=(ex.name if ex else ""),
       exercise_category=(ex.category if ex else None),
   )




def delete_item(db: DBSession, user_id: int, session_id: int, item_id: int) -> None:
   it = db.get(SessionItem, item_id)
   if not it or it.session_id != session_id:
       raise HTTPException(status_code=404, detail="Item not found")
   s = db.get(Session, session_id)
   ensure_owner(s, user_id, "session")
   db.exec(delete(SessionSet).where(SessionSet.session_item_id == item_id))
   db.exec(delete(SessionCardio).where(SessionCardio.session_item_id == item_id))
   db.delete(it)
   db.commit()




def delete_session(db: DBSession, user_id: int, session_id: int) -> None:
   s = db.get(Session, session_id)
   ensure_owner(s, user_id, "session")
   item_ids = db.exec(select(SessionItem.id).where(SessionItem.session_id == session_id)).all()
   if item_ids:
       db.exec(delete(SessionItem).where(SessionItem.id.in_(item_ids)))
   db.exec(delete(Session).where(Session.id == session_id))
   db.commit()