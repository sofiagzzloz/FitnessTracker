from pathlib import Path
from fastapi import FastAPI, Request, Depends
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
import time


from .db import init_db
from .auth import get_current_user
from .models import User
from .routers import exercises, workouts, sessions, external, auth as auth_router


app = FastAPI(title="Fitness Tracker")

# ---- CORS Configuration for Azure Deployment ----
origins = [
    "https://fitness-frontend.redglacier-88610d81.eastus.azurecontainerapps.io",
    "https://fitness-backend.redglacier-88610d81.eastus.azurecontainerapps.io",
    "http://localhost:8080",
    "http://localhost:8000",
    "http://127.0.0.1:8080",
    "http://127.0.0.1:8000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"
TEMPLATES_DIR = BASE_DIR / "templates"


app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


@app.on_event("startup")
def on_startup() -> None:
   init_db()


# ---- Metrics ----
REQUEST_COUNT = Counter(
   "http_requests_total",
   "Total HTTP requests",
   ["method", "path", "status"],
)
REQUEST_LATENCY = Histogram(
   "http_request_latency_seconds",
   "Request latency",
   ["method", "path"],
)


@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
   start = time.perf_counter()
   response = await call_next(request)
   path = request.url.path
   method = request.method
   REQUEST_COUNT.labels(method=method, path=path, status=str(response.status_code)).inc()
   REQUEST_LATENCY.labels(method=method, path=path).observe(time.perf_counter() - start)
   return response


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


# ---- Health & Metrics ----
@app.get("/health")
def health():
   return {"status": "ok"}


@app.get("/metrics")
def metrics():
   data = generate_latest()  # type: ignore
   return PlainTextResponse(data.decode("utf-8"), media_type=CONTENT_TYPE_LATEST)


# ---- Auth-required pages ----
@app.get("/", response_class=HTMLResponse)
def home(request: Request, user: User = Depends(get_current_user)):
    if user is None:
        return RedirectResponse("/login")
    return templates.TemplateResponse(request, "index.html", {"user": user})


@app.get("/exercises", response_class=HTMLResponse)
def exercises_page(request: Request, user: User = Depends(get_current_user)):
    if user is None:
        return RedirectResponse("/login")
    return templates.TemplateResponse(request, "exercises.html", {"user": user})


@app.get("/workouts", response_class=HTMLResponse)
def workouts_page(request: Request, user: User = Depends(get_current_user)):
    if user is None:
        return RedirectResponse("/login")
    return templates.TemplateResponse(request, "workouts.html", {"user": user})


@app.get("/sessions", response_class=HTMLResponse)
def sessions_page(request: Request, user: User = Depends(get_current_user)):
    if user is None:
        return RedirectResponse("/login")
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
