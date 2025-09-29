# app/main.py
from pathlib import Path

from fastapi import FastAPI, Request, Depends
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.exceptions import HTTPException as StarletteHTTPException

from .db import init_db
from .routers import exercises, workouts, sessions, external, auth as auth_router
from .auth import get_current_user
from .models import User  # only to type the dependency (optional)

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

# --- API routers ---
app.include_router(exercises.router)
app.include_router(workouts.router)
app.include_router(sessions.router)
app.include_router(external.router)
app.include_router(auth_router.router)

# ---------- Exception handler: redirect 401 HTML → /login ----------
@app.exception_handler(StarletteHTTPException)
async def http_exception_to_login(request: Request, exc: StarletteHTTPException):
    """
    If a protected HTML page raises 401 (from get_current_user),
    send the browser to /login instead of showing a JSON error.
    """
    accepts_html = "text/html" in (request.headers.get("accept") or "")
    if exc.status_code == 401 and accepts_html:
        return RedirectResponse(url="/login")
    # otherwise fall back to default behavior
    raise exc

# ---------- Public pages ----------
@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.get("/register", response_class=HTMLResponse)
def register_page(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})

# Optional: simple HTML-friendly logout that clears cookie then redirects.
@app.get("/logout")
def logout():
    resp = RedirectResponse(url="/login", status_code=302)
    # Match the name of the cookie you set in your auth router
    resp.delete_cookie("session")
    return resp

# ---------- Protected pages (require login) ----------
@app.get("/", response_class=HTMLResponse)
def home(request: Request, user: User = Depends(get_current_user)):
    # you can also pass "user" into the template if you want to show email / logout link
    return templates.TemplateResponse("index.html", {"request": request, "user": user})

@app.get("/exercises", response_class=HTMLResponse)
def exercises_page(request: Request, user: User = Depends(get_current_user)):
    return templates.TemplateResponse("exercises.html", {"request": request, "user": user})

@app.get("/workouts", response_class=HTMLResponse)
def workouts_page(request: Request, user: User = Depends(get_current_user)):
    return templates.TemplateResponse("workouts.html", {"request": request, "user": user})

@app.get("/sessions", response_class=HTMLResponse)
def sessions_page(request: Request, user: User = Depends(get_current_user)):
    return templates.TemplateResponse("sessions.html", {"request": request, "user": user})

# --- Optional tiny debug helpers (nice while wiring paths) ---
@app.get("/__debug/static-path")
def debug_static_path():
    return PlainTextResponse(str(STATIC_DIR))

@app.get("/__debug/templates-path")
def debug_templates_path():
    return PlainTextResponse(str(TEMPLATES_DIR))