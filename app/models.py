from typing import Optional
from datetime import date
from sqlmodel import SQLModel, Field

class Workout(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    date: date
    exercise: str
    sets: Optional[int] = None
    reps: Optional[int] = None
    weight_kg: Optional[float] = None
    distance_km: Optional[float] = None
    notes: Optional[str] = None

class Exercise(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)          
    category: Optional[str] = None     
    default_unit: Optional[str] = None  

