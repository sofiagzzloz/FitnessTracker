from pathlib import Path
from fastapi import FastAPI, Request, Depends
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from typing import Optional

from .db import init_db
from .auth import get_current_user , get_optional_user
from .models import User  # <- add this import
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

# APIs
app.include_router(exercises.router)
app.include_router(workouts.router)
app.include_router(sessions.router)
app.include_router(external.router)
app.include_router(auth_router.router)

# ---------- Public pages ----------
@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.get("/register", response_class=HTMLResponse)
def register_page(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})

# ---------- Auth-required pages (no manual redirects here) ----------
@app.get("/", response_class=HTMLResponse)
def home(request: Request, user: Optional[User] = Depends(get_optional_user)):
    if not user:
        return RedirectResponse("/login", status_code=303)
    return templates.TemplateResponse("index.html", {"request": request, "user": user})

@app.get("/exercises", response_class=HTMLResponse)
def exercises_page(request: Request, user: Optional[User] = Depends(get_optional_user)):
    if not user:
        return RedirectResponse("/login", status_code=303)
    return templates.TemplateResponse("exercises.html", {"request": request, "user": user})

@app.get("/workouts", response_class=HTMLResponse)
def workouts_page(request: Request, user: Optional[User] = Depends(get_optional_user)):
    if not user:
        return RedirectResponse("/login", status_code=303)
    return templates.TemplateResponse("workouts.html", {"request": request, "user": user})

@app.get("/sessions", response_class=HTMLResponse)
def sessions_page(request: Request, user: Optional[User] = Depends(get_optional_user)):
    if not user:
        return RedirectResponse("/login", status_code=303)
    return templates.TemplateResponse("sessions.html", {"request": request, "user": user})

# --- tiny debug helpers ---
@app.get("/__debug/static-path")
def debug_static_path():
    return PlainTextResponse(str(STATIC_DIR))

@app.get("/__debug/templates-path")
def debug_templates_path():
    return PlainTextResponse(str(TEMPLATES_DIR))

@app.get("/logout")
def logout_page():
    resp = RedirectResponse("/login", status_code=303)
    # IMPORTANT: delete cookie on the *same* response we return
    resp.delete_cookie(
        key="session",
        path="/",
        domain=None,   # set this if you set a domain in login
    )
    return resp