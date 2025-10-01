from pathlib import Path
from fastapi import FastAPI, Request, Depends
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .db import init_db
from .auth import get_current_user
from .models import User
from .routers import exercises, workouts, sessions, external, auth as auth_router

app = FastAPI(title="Fitness Tracker")

BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"
TEMPLATES_DIR = BASE_DIR / "templates"

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

@app.on_event("startup")
def on_startup() -> None:
    init_db()

# ---- APIs ----
app.include_router(exercises.router)
app.include_router(workouts.router)
app.include_router(sessions.router)
app.include_router(external.router)
app.include_router(auth_router.router)  # uses /api/auth/*

# ---- Public pages ----
@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse(request, "login.html", {"user": None})

@app.get("/register", response_class=HTMLResponse)
def register_page(request: Request):
    return templates.TemplateResponse(request, "register.html", {"user": None})

# ---- Auth-required pages ----
@app.get("/", response_class=HTMLResponse)
def home(request: Request, user: User = Depends(get_current_user)):
    return templates.TemplateResponse(request, "index.html", {"user": user})

@app.get("/exercises", response_class=HTMLResponse)
def exercises_page(request: Request, user: User = Depends(get_current_user)):
    return templates.TemplateResponse(request, "exercises.html", {"user": user})

@app.get("/workouts", response_class=HTMLResponse)
def workouts_page(request: Request, user: User = Depends(get_current_user)):
    return templates.TemplateResponse(request, "workouts.html", {"user": user})

@app.get("/sessions", response_class=HTMLResponse)
def sessions_page(request: Request, user: User = Depends(get_current_user)):
    return templates.TemplateResponse(request, "sessions.html", {"user": user})

# ---- Debug helpers ----
@app.get("/__debug/static-path")
def debug_static_path():
    return PlainTextResponse(str(STATIC_DIR))

@app.get("/__debug/templates-path")
def debug_templates_path():
    return PlainTextResponse(str(TEMPLATES_DIR))

# ---- Logout page route: clear BOTH cookie names then redirect ----
@app.get("/logout")
def logout_page():
    resp = RedirectResponse("/login", status_code=303)
    for name in ("access_token", "session"):
        resp.delete_cookie(key=name, path="/")
    return resp