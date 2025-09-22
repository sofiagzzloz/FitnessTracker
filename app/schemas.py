from typing import Optional
from datetime import date, datetime
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
    date: Optional[date] = None # type: ignore 
    exercise_id: Optional[int] = None
    sets: Optional[int] = None
    reps: Optional[int] = None
    weight_kg: Optional[float] = None
    distance_km: Optional[float] = None
    notes: Optional[str] = None

    model_config = {
        "json_schema_extra": {
            "examples": [
                {"sets": 3, "reps": 10},
                {"weight_kg": 10},
                {"exercise_id": 5, "notes": "bigger"}
            ]
        }
    }

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

class SessionCreate(BaseModel):
    date: date
    title: Optional[str] = None
    notes: Optional[str] = None

class SessionRead(BaseModel):
    id: int
    date: date
    title: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime

class SessionItemCreate(BaseModel):
    exercise_id: int
    notes: Optional[str] = None
    order_index: Optional[int] = None

class SessionItemRead(BaseModel):
    id: int
    session_id: int
    exercise_id: int
    notes: Optional[str] = None
    order_index: Optional[int] = None
    exercise_name: str
    exercise_category: Optional[str] = None

    