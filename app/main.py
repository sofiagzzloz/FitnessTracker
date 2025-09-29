from pathlib import Path
from fastapi import FastAPI, Request, Depends
from fastapi.responses import HTMLResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

# Auth
from .routers import auth as auth_router
from .auth import get_current_user

# DB bootstrap
from .db import init_db

# API routers
from .routers import exercises, workouts, sessions, external

app = FastAPI(title="Fitness Tracker")

# --- Paths ---
BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"
TEMPLATES_DIR = BASE_DIR / "templates"

# --- Static + Templates ---
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# --- DB init ---
@app.on_event("startup")
def on_startup() -> None:
    init_db()

# --- Routers ---
# Auth is open
app.include_router(auth_router.router)

# Everything else requires login
app.include_router(exercises.router, dependencies=[Depends(get_current_user)])
app.include_router(workouts.router,  dependencies=[Depends(get_current_user)])
app.include_router(sessions.router,  dependencies=[Depends(get_current_user)])
app.include_router(external.router,  dependencies=[Depends(get_current_user)])

# --- Page routes ---
@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.get("/exercises", response_class=HTMLResponse, dependencies=[Depends(get_current_user)])
def exercises_page(request: Request):
    return templates.TemplateResponse("exercises.html", {"request": request})

@app.get("/workouts", response_class=HTMLResponse, dependencies=[Depends(get_current_user)])
def workouts_page(request: Request):
    return templates.TemplateResponse("workouts.html", {"request": request})

@app.get("/sessions", response_class=HTMLResponse, dependencies=[Depends(get_current_user)])
def sessions_page(request: Request):
    return templates.TemplateResponse("sessions.html", {"request": request})

# --- Debug helpers ---
@app.get("/__debug/static-path")
def debug_static_path():
    return PlainTextResponse(str(STATIC_DIR))

@app.get("/__debug/templates-path")
def debug_templates_path():
    return PlainTextResponse(str(TEMPLATES_DIR))

@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.get("/register", response_class=HTMLResponse)
def register_page(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})