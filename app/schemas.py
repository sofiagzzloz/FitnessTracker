from typing import Optional
from datetime import date
from pydantic import BaseModel, Field

class WorkoutCreate(BaseModel):
    date: date
    exercise_id: int
    sets: Optional[int] = None
    reps: Optional[int] = None
    weight_kg: Optional[float] = None
    distance_km: Optional[float] = None
    notes: Optional[str] = None

class WorkoutRead(BaseModel):
    id: int
    date: date
    exercise_id: int
    sets: Optional[int] = None
    reps: Optional[int] = None
    weight_kg: Optional[float] = None
    distance_km: Optional[float] = None
    notes: Optional[str] = None

    exercise_name: str
    exercise_category: Optional[str] = None

class WorkoutUpdate(BaseModel):
    date: Optional[date]
    exercise: Optional[int] = None
    sets: Optional[int] = None
    reps: Optional[int] = None
    weight_kg: Optional[float] = None
    distance_km: Optional[float] = None
    notes: Optional[str] = None

class ExerciseCreate(BaseModel):
    name: str = Field(min_length=1)
    category: Optional[str] = None
    default_unit: Optional[str] = None

class ExerciseRead(ExerciseCreate):
    id: int

class ExerciseUpdate(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    default_unit: Optional[str] = None