from __future__ import annotations
from typing import Optional
import datetime as dt
from enum import Enum
from sqlmodel import SQLModel, Field


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


# ---------- Master user ----------
class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(index=True, unique=True)
    password_hash: str
    created_at: dt.datetime = Field(default_factory=dt.datetime.utcnow)


# ---------- Exercises & Muscles ----------
class Exercise(SQLModel, table=True):
    """
    Library of movements. Now scoped by user_id.
    """
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)   # <-- added
    name: str = Field(index=True)
    category: Category = Field(default=Category.strength)
    default_unit: Optional[str] = None
    equipment: Optional[str] = None
    source: str = Field(default="local")
    source_ref: Optional[str] = None


class Muscle(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    slug: str = Field(index=True)


class ExerciseMuscle(SQLModel, table=True):
    exercise_id: int = Field(foreign_key="exercise.id", primary_key=True)
    muscle_id: int = Field(foreign_key="muscle.id", primary_key=True)
    role: MuscleRole = Field(default=MuscleRole.primary)


# ---------- Workout Templates (Plans) ----------
class WorkoutTemplate(SQLModel, table=True):
    """
    Blueprint you build once and reuse. Scoped by user_id.
    """
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)   # <-- added
    name: str
    notes: Optional[str] = None
    created_at: dt.datetime = Field(default_factory=dt.datetime.utcnow)
    updated_at: dt.datetime = Field(default_factory=dt.datetime.utcnow)


class WorkoutItem(SQLModel, table=True):
    """
    Items live under a template. We don't store user_id here because
    ownership comes via the parent template.
    """
    id: Optional[int] = Field(default=None, primary_key=True)
    workout_template_id: int = Field(foreign_key="workouttemplate.id", index=True)
    order_index: int = Field(default=0, index=True)
    exercise_id: int = Field(foreign_key="exercise.id", index=True)

    # Planned for strength
    planned_sets: Optional[int] = None
    planned_reps: Optional[int] = None
    planned_weight: Optional[float] = None
    planned_rpe: Optional[float] = None

    # Planned for cardio
    planned_minutes: Optional[int] = None
    planned_distance: Optional[float] = None
    planned_distance_unit: Optional[str] = None

    notes: Optional[str] = None
    created_at: dt.datetime = Field(default_factory=dt.datetime.utcnow)
    updated_at: dt.datetime = Field(default_factory=dt.datetime.utcnow)


# ---------- Sessions (Logged / Performed) ----------
class Session(SQLModel, table=True):
    """
    Actual workouts tied to a date. Scoped by user_id.
    """
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)   # <-- added
    date: dt.date = Field(index=True)
    title: Optional[str] = None
    notes: Optional[str] = None
    workout_template_id: Optional[int] = Field(default=None, foreign_key="workouttemplate.id")
    status: SessionStatus = Field(default=SessionStatus.completed)
    created_at: dt.datetime = Field(default_factory=dt.datetime.utcnow)
    updated_at: dt.datetime = Field(default_factory=dt.datetime.utcnow)


class SessionItem(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    session_id: int = Field(foreign_key="session.id", index=True)
    order_index: int = Field(default=0, index=True)
    exercise_id: int = Field(foreign_key="exercise.id", index=True)
    notes: Optional[str] = None
    created_at: dt.datetime = Field(default_factory=dt.datetime.utcnow)
    updated_at: dt.datetime = Field(default_factory=dt.datetime.utcnow)


class SessionSet(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    session_item_id: int = Field(foreign_key="sessionitem.id", index=True)
    set_number: int = Field(default=1)
    reps: Optional[int] = None
    weight: Optional[float] = None
    rpe: Optional[float] = None


class SessionCardio(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    session_item_id: int = Field(foreign_key="sessionitem.id", index=True)
    minutes: Optional[int] = None
    distance: Optional[float] = None
    distance_unit: Optional[str] = None
    avg_hr: Optional[int] = None
    avg_pace: Optional[str] = None
