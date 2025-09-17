from fastapi import FastAPI
from .db import init_db

app = FastAPI(title= "Fitness Tracker")

@app.on_event("startup")
def on_startup():
    init_db()

@app.get("/")
def read_root():
    return {"message: Welcome to the Fitness Tracker"}

