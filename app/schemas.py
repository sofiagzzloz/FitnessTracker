from typing import Optional
from datetime import date, datetime
from pydantic import BaseModel
from enum import Enum


# ---------- Enums ----------
class Category(str, Enum):
    strength = "strength"
    cardio = "cardio"
    mobility = "mobility"


class MuscleRole(str, Enum):
    primary = "primary"
    secondary = "secondary"


class SessionStatus(str, Enum):
    draft = "draft"
    completed = "completed"


# ---------- Exercises ----------
class ExerciseCreate(BaseModel):
    name: str
    category: Category
    default_unit: Optional[str] = None
    equipment: Optional[str] = None


class ExerciseRead(ExerciseCreate):
    id: int
    source: str
    source_ref: Optional[str] = None


class ExerciseUpdate(BaseModel):
    name: Optional[str] = None
    category: Optional[Category] = None
    default_unit: Optional[str] = None
    equipment: Optional[str] = None


# ---------- Muscles ----------
class MuscleRead(BaseModel):
    id: int
    name: str
    slug: str


# ---------- Workout Templates ----------
class WorkoutTemplateCreate(BaseModel):
    name: str
    notes: Optional[str] = None


class WorkoutTemplateRead(WorkoutTemplateCreate):
    id: int
    created_at: datetime
    updated_at: datetime


class WorkoutItemCreate(BaseModel):
    exercise_id: int
    order_index: Optional[int] = 0
    # planned (strength)
    planned_sets: Optional[int] = None
    planned_reps: Optional[int] = None
    planned_weight: Optional[float] = None
    planned_rpe: Optional[float] = None
    # planned (cardio)
    planned_minutes: Optional[int] = None
    planned_distance: Optional[float] = None
    planned_distance_unit: Optional[str] = None
    notes: Optional[str] = None


class WorkoutItemRead(WorkoutItemCreate):
    id: int
    workout_template_id: int
    created_at: datetime
    updated_at: datetime


# ---------- Sessions ----------
class SessionCreate(BaseModel):
    date: date
    title: Optional[str] = None
    notes: Optional[str] = None
    workout_template_id: Optional[int] = None


class SessionRead(SessionCreate):
    id: int
    status: SessionStatus
    created_at: datetime
    updated_at: datetime


class SessionItemCreate(BaseModel):
    exercise_id: int
    order_index: Optional[int] = 0
    notes: Optional[str] = None


class SessionItemRead(BaseModel):
    id: int
    session_id: int
    exercise_id: int
    notes: Optional[str]
    order_index: Optional[int]
    exercise_name: str
    exercise_category: Optional[str]
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

# ---------- Strength Sets ----------
class SessionSetCreate(BaseModel):
    set_number: int
    reps: Optional[int] = None
    weight: Optional[float] = None
    rpe: Optional[float] = None


class SessionSetRead(SessionSetCreate):
    id: int
    session_item_id: int


# ---------- Cardio Metrics ----------
class SessionCardioUpdate(BaseModel):
    minutes: Optional[int] = None
    distance: Optional[float] = None
    distance_unit: Optional[str] = None
    avg_hr: Optional[int] = None
    avg_pace: Optional[str] = None


class SessionCardioRead(SessionCardioUpdate):
    id: int
    session_item_id: int