from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from .db import init_db
from .routers import workouts, exercises, sessions
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

app = FastAPI(title= "Fitness Tracker")

@app.on_event("startup")
def on_startup():
    init_db()

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

app.include_router(workouts.router)
app.include_router(exercises.router)
app.include_router(sessions.router)

@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/exercises", response_class=HTMLResponse)
def exercises_page(request: Request):
    return templates.TemplateResponse("exercises.html", {"request": request})

@app.get("/workouts", response_class=HTMLResponse)
def workouts_page(request: Request):
    return templates.TemplateResponse("workouts.html", {"request": request})

@app.get("/sessions", response_class=HTMLResponse)
def sessions_page(request: Request):
    return templates.TemplateResponse("sessions.html", {"request": request})

