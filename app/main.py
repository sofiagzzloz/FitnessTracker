from fastapi import FastAPI
from .db import init_db
from .routers import workouts, exercises

app = FastAPI(title= "Fitness Tracker")

@app.on_event("startup")
def on_startup():
    init_db()
app.include_router(workouts.router)
app.include_router(exercises.router)

@app.get("/")
def read_root():
    return {"message: Welcome to the Fitness Tracker"}

