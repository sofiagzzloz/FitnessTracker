from __future__ import annotations
from typing import Optional
from datetime import date, datetime
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
    completed = "completed"   # you log after doing it


# ---------- Exercises & Muscles ----------
class Exercise(SQLModel, table=True):
    """
    Library of movements. Can be user-created or imported from an external provider.
    """
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    category: Category = Field(default=Category.strength)
    default_unit: Optional[str] = None      # e.g., "kg", "lb", "km", "min"
    equipment: Optional[str] = None
    source: str = Field(default="local")    # "local" | "wger" | "exercisedb" | ...
    source_ref: Optional[str] = None        # external id, if imported


class Muscle(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)           # e.g., "Quadriceps"
    slug: str = Field(index=True)           # e.g., "quads"


class ExerciseMuscle(SQLModel, table=True):
    """
    Join table: which muscles an exercise hits, and whether primary/secondary.
    """
    exercise_id: int = Field(foreign_key="exercise.id", primary_key=True)
    muscle_id: int = Field(foreign_key="muscle.id", primary_key=True)
    role: MuscleRole = Field(default=MuscleRole.primary)


# ---------- Workout Templates (Plans) ----------
class WorkoutTemplate(SQLModel, table=True):
    """
    Blueprint you build once and reuse. Not tied to a date.
    """
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class WorkoutItem(SQLModel, table=True):
    """
    An entry inside a workout template. Strength and cardio planned fields are optional.
    """
    id: Optional[int] = Field(default=None, primary_key=True)
    workout_template_id: int = Field(foreign_key="workouttemplate.id", index=True)
    order_index: int = Field(default=0, index=True)
    exercise_id: int = Field(foreign_key="exercise.id", index=True)

    # Planned for strength
    planned_sets: Optional[int] = None
    planned_reps: Optional[int] = None
    planned_weight: Optional[float] = None      # kg or lb — UI should respect exercise.default_unit
    planned_rpe: Optional[float] = None

    # Planned for cardio
    planned_minutes: Optional[int] = None
    planned_distance: Optional[float] = None
    planned_distance_unit: Optional[str] = None  # "km", "mi", etc.

    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


# ---------- Sessions (Logged / Performed) ----------
class Session(SQLModel, table=True):
    """
    A record of what you actually did. Must be for today or a past date (enforce in API).
    """
    id: Optional[int] = Field(default=None, primary_key=True)
    date: date = Field(index=True)
    title: Optional[str] = None
    notes: Optional[str] = None
    workout_template_id: Optional[int] = Field(default=None, foreign_key="workouttemplate.id")
    status: SessionStatus = Field(default=SessionStatus.completed)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class SessionItem(SQLModel, table=True):
    """
    An exercise performed inside a session, in order.
    """
    id: Optional[int] = Field(default=None, primary_key=True)
    session_id: int = Field(foreign_key="session.id", index=True)
    order_index: int = Field(default=0, index=True)
    exercise_id: int = Field(foreign_key="exercise.id", index=True)
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class SessionSet(SQLModel, table=True):
    """
    Strength actuals: one row per set.
    """
    id: Optional[int] = Field(default=None, primary_key=True)
    session_item_id: int = Field(foreign_key="sessionitem.id", index=True)
    set_number: int = Field(default=1)          # 1-based
    reps: Optional[int] = None
    weight: Optional[float] = None              # same unit choice as exercise.default_unit
    rpe: Optional[float] = None


class SessionCardio(SQLModel, table=True):
    """
    Cardio actuals: one row per session item (or extend later for laps/intervals).
    """
    id: Optional[int] = Field(default=None, primary_key=True)
    session_item_id: int = Field(foreign_key="sessionitem.id", index=True)
    minutes: Optional[int] = None
    distance: Optional[float] = None
    distance_unit: Optional[str] = None
    avg_hr: Optional[int] = None
    avg_pace: Optional[str] = None             # store "mm:ss/km" as text for now