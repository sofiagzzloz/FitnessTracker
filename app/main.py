from fastapi import FastAPI
from .db import init_db
from .routers import workouts

app = FastAPI(title= "Fitness Tracker")

@app.on_event("startup")
def on_startup():
    init_db()
app.include_router(workouts.router)

@app.get("/")
def read_root():
    return {"message: Welcome to the Fitness Tracker"}

