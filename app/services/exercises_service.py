from __future__ import annotations
from typing import List, Optional, Dict, Any
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session as DBSession, select
from fastapi import HTTPException


from ..models import Exercise, WorkoutItem, SessionItem, Category, WorkoutTemplate, Session, ExerciseMuscle
from ..schemas import ExerciseCreate, ExerciseUpdate
from .common import ensure_owner, normalize_whitespace, case_insensitive_equal




def create_exercise(db: DBSession, user_id: int, payload: ExerciseCreate) -> Exercise:
   if not payload.name or not payload.name.strip():
       raise HTTPException(status_code=400, detail="Name is required")


   norm_name = normalize_whitespace(payload.name)


   dup = db.exec(
       select(Exercise)
       .where(Exercise.user_id == user_id)
       .where(func.lower(Exercise.name) == (norm_name or "").lower())
   ).first()
   if dup:
       raise HTTPException(status_code=409, detail="Exercise with that name already exists")


   ex = Exercise(
       user_id=user_id,
       name=norm_name or "",
       category=payload.category,
       default_unit=normalize_whitespace(payload.default_unit),
       equipment=normalize_whitespace(payload.equipment),
       source="local",
       source_ref=None,
   )
   db.add(ex)
   db.commit()
   db.refresh(ex)
   return ex




def list_exercises(
   db: DBSession,
   user_id: int,
   q: Optional[str],
   category: Optional[Category],
   limit: int,
   offset: int,
) -> List[Exercise]:
   stmt = select(Exercise).where(Exercise.user_id == user_id)
   if q:
       stmt = stmt.where(func.lower(Exercise.name).like(f"%{q.lower()}%"))
   if category is not None:
       stmt = stmt.where(Exercise.category == category)
   stmt = stmt.order_by(Exercise.id.desc()).limit(limit).offset(offset)
   return db.exec(stmt).all()




def get_exercise(db: DBSession, user_id: int, exercise_id: int) -> Exercise:
   ex = db.get(Exercise, exercise_id)
   ensure_owner(ex, user_id, "exercise")
   return ex  # type: ignore




def update_exercise(
   db: DBSession,
   user_id: int,
   exercise_id: int,
   payload: ExerciseUpdate,
) -> Exercise:
   ex = db.get(Exercise, exercise_id)
   ensure_owner(ex, user_id, "exercise")
   assert ex is not None


   data = payload.model_dump(exclude_unset=True)


   if "name" in data and data["name"] is not None:
       new_name = normalize_whitespace(data["name"]) or ""
       if not new_name:
           raise HTTPException(status_code=400, detail="Name cannot be empty")
       if not case_insensitive_equal(new_name, ex.name):
           dup = db.exec(
               select(Exercise)
               .where(Exercise.user_id == user_id)
               .where(func.lower(Exercise.name) == new_name.lower())
           ).first()
           if dup:
               raise HTTPException(status_code=409, detail="Exercise with that name already exists")
       ex.name = new_name


   if "category" in data:
       ex.category = data["category"] or ex.category
   if "default_unit" in data:
       ex.default_unit = normalize_whitespace(data["default_unit"])  # type: ignore
   if "equipment" in data:
       ex.equipment = normalize_whitespace(data["equipment"])  # type: ignore


   db.add(ex)
   db.commit()
   db.refresh(ex)
   return ex




def delete_exercise(db: DBSession, user_id: int, exercise_id: int) -> None:
   ex = db.get(Exercise, exercise_id)
   ensure_owner(ex, user_id, "exercise")
   assert ex is not None


   try:
       links = db.exec(select(ExerciseMuscle).where(ExerciseMuscle.exercise_id == exercise_id)).all()
       for link in links:
           db.delete(link)
       db.flush()


       db.delete(ex)
       db.commit()
   except IntegrityError:
       db.rollback()
       raise HTTPException(status_code=409, detail="Cannot delete exercise: it is referenced by workouts/sessions.")




def get_exercise_usage(db: DBSession, user_id: int, exercise_id: int) -> Dict[str, Any]:
   ex = db.get(Exercise, exercise_id)
   ensure_owner(ex, user_id, "exercise")
   assert ex is not None


   wq = (
       select(WorkoutTemplate)
       .where(WorkoutTemplate.user_id == user_id)
       .join(WorkoutItem, WorkoutItem.workout_template_id == WorkoutTemplate.id)
       .where(WorkoutItem.exercise_id == exercise_id)
       .order_by(WorkoutTemplate.name.asc())
   )
   workouts = db.exec(wq).all()


   sq = (
       select(Session)
       .where(Session.user_id == user_id)
       .join(SessionItem, SessionItem.session_id == Session.id)
       .where(SessionItem.exercise_id == exercise_id)
       .order_by(Session.date.desc())
   )
   sessions_rows = db.exec(sq).all()


   return {
       "exercise": {"id": ex.id, "name": ex.name},
       "workouts": [{"id": w.id, "name": w.name} for w in workouts],
       "sessions": [{"id": s.id, "title": s.title, "date": str(s.date)} for s in sessions_rows],
       "counts": {"workouts": len(workouts), "sessions": len(sessions_rows)},
   }
