from __future__ import annotations
from typing import List, Optional
from pydantic import BaseModel
from fastapi import HTTPException
from sqlalchemy import func
from sqlmodel import Session as DBSession, select


from ..models import (
   WorkoutTemplate,
   WorkoutItem,
   Exercise,
   Session,
   SessionItem,
   Muscle,
   ExerciseMuscle,
)
from ..schemas import (
   WorkoutTemplateCreate,
   WorkoutTemplateRead,
   WorkoutItemCreate,
   WorkoutItemRead,
   SessionRead,
)
from .common import ensure_owner




def list_templates(db: DBSession, user_id: int, q: Optional[str]) -> List[WorkoutTemplate]:
   stmt = select(WorkoutTemplate).where(WorkoutTemplate.user_id == user_id)
   if q:
       stmt = stmt.where(func.lower(WorkoutTemplate.name).like(f"%{q.lower()}%"))
   stmt = stmt.order_by(WorkoutTemplate.id.desc())
   return db.exec(stmt).all()




def create_template(db: DBSession, user_id: int, payload: WorkoutTemplateCreate) -> WorkoutTemplate:
   name = (payload.name or "").strip()
   if not name:
       raise HTTPException(status_code=400, detail="name is required")
   t = WorkoutTemplate(name=name, notes=(payload.notes or None), user_id=user_id)
   db.add(t)
   db.commit()
   db.refresh(t)
   return t




def get_template(db: DBSession, user_id: int, template_id: int) -> WorkoutTemplate:
   t = db.get(WorkoutTemplate, template_id)
   ensure_owner(t, user_id, "template")
   return t  # type: ignore




def delete_template(db: DBSession, user_id: int, template_id: int) -> None:
   t = db.get(WorkoutTemplate, template_id)
   ensure_owner(t, user_id, "template")
   items = db.exec(select(WorkoutItem).where(WorkoutItem.workout_template_id == template_id)).all()
   for it in items:
       db.delete(it)
   db.delete(t)
   db.commit()




def list_template_items(db: DBSession, user_id: int, template_id: int) -> List[WorkoutItem]:
   t = db.get(WorkoutTemplate, template_id)
   ensure_owner(t, user_id, "template")
   stmt = (
       select(WorkoutItem)
       .where(WorkoutItem.workout_template_id == template_id)
       .order_by(WorkoutItem.order_index.asc(), WorkoutItem.id.asc())
   )
   return db.exec(stmt).all()




def add_template_item(db: DBSession, user_id: int, template_id: int, payload: WorkoutItemCreate) -> WorkoutItem:
   t = db.get(WorkoutTemplate, template_id)
   ensure_owner(t, user_id, "template")


   ex = db.get(Exercise, payload.exercise_id)
   if not ex or ex.user_id != user_id:
       raise HTTPException(status_code=404, detail="exercise not found")


   cur_max = db.exec(
       select(func.max(WorkoutItem.order_index)).where(WorkoutItem.workout_template_id == template_id)
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




def update_template_item(db: DBSession, user_id: int, item_id: int, payload: WorkoutItemUpdate) -> WorkoutItem:
   it = db.get(WorkoutItem, item_id)
   if not it:
       raise HTTPException(status_code=404, detail="item not found")
   t = db.get(WorkoutTemplate, it.workout_template_id)
   ensure_owner(t, user_id, "template")


   data = payload.model_dump(exclude_unset=True)
   for field, value in data.items():
       setattr(it, field, value)


   db.add(it)
   db.commit()
   db.refresh(it)
   return it




def delete_template_item(db: DBSession, user_id: int, item_id: int) -> None:
   it = db.get(WorkoutItem, item_id)
   if not it:
       raise HTTPException(status_code=404, detail="item not found")
   t = db.get(WorkoutTemplate, it.workout_template_id)
   ensure_owner(t, user_id, "template")


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




def make_session_from_template(
   db: DBSession,
   user_id: int,
   template_id: int,
   session_date,
   title: Optional[str],
   notes: Optional[str],
) -> Session:
   from .common import today
   if session_date > today():
       raise HTTPException(status_code=422, detail="You can only log sessions for today or earlier.")
   t = db.get(WorkoutTemplate, template_id)
   ensure_owner(t, user_id, "template")


   ss = Session(
       user_id=user_id,
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




def template_muscles(db: DBSession, user_id: int, template_id: int):
   t = db.get(WorkoutTemplate, template_id)
   ensure_owner(t, user_id, "template")


   items = db.exec(select(WorkoutItem).where(WorkoutItem.workout_template_id == template_id)).all()
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




def resequence_template(db: DBSession, user_id: int, template_id: int) -> None:
   t = db.get(WorkoutTemplate, template_id)
   ensure_owner(t, user_id, "template")


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