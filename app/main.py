from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

# our DB bootstrap
from .db import init_db

# API routers (ensure these files define APIRouter instances)
from .routers import exercises, workouts, sessions, external # add others as you create them

app = FastAPI(title="Fitness Tracker")

# --- Resolve absolute paths so it works no matter where uvicorn is launched ---
BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"
TEMPLATES_DIR = BASE_DIR / "templates"

# --- Static + Templates ---
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# --- DB init on startup ---
@app.on_event("startup")
def on_startup() -> None:
    init_db()

# --- API routers (all API endpoints live under /api/...) ---
# IMPORTANT: your exercises router should have prefix="/api/exercises", etc.
app.include_router(exercises.router)
app.include_router(workouts.router)
app.include_router(sessions.router)
app.include_router(external.router)

# --- Page routes (HTML) ---
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

# --- Optional tiny debug helpers (nice while wiring paths) ---
@app.get("/__debug/static-path")
def debug_static_path():
    return PlainTextResponse(str(STATIC_DIR))

@app.get("/__debug/templates-path")
def debug_templates_path():
    return PlainTextResponse(str(TEMPLATES_DIR))