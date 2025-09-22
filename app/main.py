# app/main.py
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, PlainTextResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pathlib import Path
from typing import Dict, List, Optional

# Simple in-memory storage. In a real app, use a database.
class MemoryDB:
    def __init__(self) -> None:
        self.exercise_seq: int = 1
        self.exercises: Dict[int, Dict] = {}

        self.template_seq: int = 1
        self.templates: Dict[int, Dict] = {}
        # template_id -> list of items
        self.template_items: Dict[int, List[Dict]] = {}
        self.template_item_seq: int = 1

        self.session_seq: int = 1
        self.sessions: Dict[int, Dict] = {}
        # session_id -> list of items
        self.session_items: Dict[int, List[Dict]] = {}
        self.session_item_seq: int = 1

    # --- Exercises ---
    def list_exercises(self, q: Optional[str], category: Optional[str]) -> List[Dict]:
        items = list(self.exercises.values())
        if q:
            ql = q.lower()
            items = [e for e in items if ql in e["name"].lower()]
        if category:
            cl = category.lower()
            items = [e for e in items if e.get("category", "").lower() == cl]
        # sort by id asc
        items.sort(key=lambda e: e["id"])
        return items

    def create_exercise(self, name: str, category: str, unit: Optional[str]) -> Dict:
        ex = {"id": self.exercise_seq, "name": name, "category": category, "unit": unit or ""}
        self.exercises[self.exercise_seq] = ex
        self.exercise_seq += 1
        return ex

    # --- Templates (Workouts) ---
    def list_templates(self) -> List[Dict]:
        items = list(self.templates.values())
        items.sort(key=lambda t: t["id"]) 
        return items

    def create_template(self, name: str, notes: Optional[str]) -> Dict:
        t = {"id": self.template_seq, "name": name, "notes": notes or ""}
        self.templates[self.template_seq] = t
        self.template_items[self.template_seq] = []
        self.template_seq += 1
        return t

    def delete_template(self, template_id: int) -> None:
        if template_id in self.templates:
            del self.templates[template_id]
            self.template_items.pop(template_id, None)
        else:
            raise KeyError("template not found")

    def add_template_item(self, template_id: int, exercise_id: int, notes: Optional[str], planned: Optional[str] = None) -> Dict:
        if template_id not in self.templates:
            raise KeyError("template not found")
        if exercise_id not in self.exercises:
            raise KeyError("exercise not found")
        item = {
            "id": self.template_item_seq,
            "order": len(self.template_items.get(template_id, [])) + 1,
            "template_id": template_id,
            "exercise_id": exercise_id,
            "exercise_name": self.exercises[exercise_id]["name"],
            "notes": notes or "",
            "planned": planned or "",
        }
        self.template_items.setdefault(template_id, []).append(item)
        self.template_item_seq += 1
        return item

    def list_template_items(self, template_id: int) -> List[Dict]:
        return list(self.template_items.get(template_id, []))

    def update_template_item(self, template_id: int, item_id: int, *, planned: Optional[str]=None, notes: Optional[str]=None) -> Dict:
        items = self.template_items.get(template_id, [])
        for it in items:
            if it["id"] == item_id:
                if planned is not None:
                    it["planned"] = planned
                if notes is not None:
                    it["notes"] = notes
                return it
        raise KeyError("item not found")

    def delete_template_item(self, template_id: int, item_id: int) -> None:
        items = self.template_items.get(template_id, [])
        idx = next((i for i, it in enumerate(items) if it["id"] == item_id), None)
        if idx is None:
            raise KeyError("item not found")
        items.pop(idx)
        # re-number order
        for i, it in enumerate(items, start=1):
            it["order"] = i

    # --- Sessions ---
    def list_sessions(self) -> List[Dict]:
        items = list(self.sessions.values())
        items.sort(key=lambda s: s["id"]) 
        return items

    def create_session(self, date: str, title: str, notes: Optional[str]) -> Dict:
        s = {"id": self.session_seq, "date": date, "title": title, "notes": notes or ""}
        self.sessions[self.session_seq] = s
        self.session_items[self.session_seq] = []
        self.session_seq += 1
        return s

    def add_session_item(self, session_id: int, exercise_id: int, order: Optional[int], notes: Optional[str]) -> Dict:
        if session_id not in self.sessions:
            raise KeyError("session not found")
        if exercise_id not in self.exercises:
            raise KeyError("exercise not found")
        items = self.session_items.setdefault(session_id, [])
        item = {
            "id": self.session_item_seq,
            "order": int(order) if order else len(items) + 1,
            "session_id": session_id,
            "exercise_id": exercise_id,
            "exercise_name": self.exercises[exercise_id]["name"],
            "notes": notes or "",
        }
        items.append(item)
        self.session_item_seq += 1
        return item

    def list_session_items(self, session_id: int) -> List[Dict]:
        return list(self.session_items.get(session_id, []))

    def create_session_from_template(self, template_id: int, date: str, title: str, notes: Optional[str]) -> Dict:
        if template_id not in self.templates:
            raise KeyError("template not found")
        # default title if empty
        base_title = self.templates[template_id]["name"]
        s = self.create_session(date=date, title=title or base_title, notes=notes)
        sid = s["id"]
        for idx, t_item in enumerate(self.template_items.get(template_id, []), start=1):
            self.add_session_item(
                session_id=sid,
                exercise_id=t_item["exercise_id"],
                order=idx,
                notes=t_item.get("notes", ""),
            )
        return s

app = FastAPI(title="Fitness Tracker")

# Resolve absolute project paths no matter where uvicorn is launched from
BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"
TEMPLATES_DIR = BASE_DIR / "templates"

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
db = MemoryDB()

# ---- (your routers / API mounts here) ----
@app.get("/api/exercises")
def api_list_exercises(q: Optional[str] = None, category: Optional[str] = None):
    return JSONResponse(db.list_exercises(q, category))

@app.post("/api/exercises")
async def api_create_exercise(request: Request):
    data = await request.json()
    name = (data.get("name") or "").strip()
    category = (data.get("category") or "").strip()
    unit = (data.get("unit") or "").strip()
    if not name or not category:
        raise HTTPException(status_code=400, detail={"error": "name and category are required"})
    ex = db.create_exercise(name=name, category=category, unit=unit)
    return JSONResponse(ex, status_code=201)

@app.get("/api/workouts/templates")
def api_list_templates():
    return JSONResponse(db.list_templates())

@app.post("/api/workouts/templates")
async def api_create_template(request: Request):
    data = await request.json()
    name = (data.get("name") or "").strip()
    notes = (data.get("notes") or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail={"error": "name is required"})
    t = db.create_template(name=name, notes=notes)
    return JSONResponse(t, status_code=201)

@app.delete("/api/workouts/templates/{template_id}")
def api_delete_template(template_id: int):
    try:
        db.delete_template(template_id)
    except KeyError:
        raise HTTPException(status_code=404, detail={"error": "template not found"})
    return JSONResponse({"ok": True})

@app.get("/api/workouts/templates/{template_id}/items")
def api_list_template_items(template_id: int):
    return JSONResponse(db.list_template_items(template_id))

@app.post("/api/workouts/templates/{template_id}/items")
async def api_add_template_item(template_id: int, request: Request):
    data = await request.json()
    exercise_id = data.get("exercise_id")
    notes = (data.get("notes") or "").strip()
    planned = (data.get("planned") or "").strip()
    if not exercise_id:
        raise HTTPException(status_code=400, detail={"error": "exercise_id required"})
    try:
        item = db.add_template_item(template_id=template_id, exercise_id=int(exercise_id), notes=notes, planned=planned)
    except KeyError as e:
        raise HTTPException(status_code=404, detail={"error": str(e)})
    return JSONResponse(item, status_code=201)

@app.put("/api/workouts/templates/{template_id}/items/{item_id}")
async def api_update_template_item(template_id: int, item_id: int, request: Request):
    data = await request.json()
    planned = data.get("planned")
    notes = data.get("notes")
    try:
        item = db.update_template_item(template_id=template_id, item_id=item_id, planned=planned, notes=notes)
    except KeyError as e:
        raise HTTPException(status_code=404, detail={"error": str(e)})
    return JSONResponse(item)

@app.delete("/api/workouts/templates/{template_id}/items/{item_id}")
def api_delete_template_item(template_id: int, item_id: int):
    try:
        db.delete_template_item(template_id=template_id, item_id=item_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail={"error": str(e)})
    return JSONResponse({"ok": True})

@app.get("/api/sessions")
def api_list_sessions():
    return JSONResponse(db.list_sessions())

@app.post("/api/sessions")
async def api_create_session(request: Request):
    data = await request.json()
    date = (data.get("date") or "").strip()
    title = (data.get("title") or "").strip()
    notes = (data.get("notes") or "").strip()
    if not date or not title:
        raise HTTPException(status_code=400, detail={"error": "date and title are required"})
    s = db.create_session(date=date, title=title, notes=notes)
    return JSONResponse(s, status_code=201)

@app.get("/api/sessions/{session_id}/items")
def api_list_session_items(session_id: int):
    return JSONResponse(db.list_session_items(session_id))

@app.post("/api/sessions/{session_id}/items")
async def api_add_session_item(session_id: int, request: Request):
    data = await request.json()
    exercise_id = data.get("exercise_id")
    order = data.get("order")
    notes = (data.get("notes") or "").strip()
    if not exercise_id:
        raise HTTPException(status_code=400, detail={"error": "exercise_id required"})
    try:
        item = db.add_session_item(session_id=int(session_id), exercise_id=int(exercise_id), order=order, notes=notes)
    except KeyError as e:
        raise HTTPException(status_code=404, detail={"error": str(e)})
    return JSONResponse(item, status_code=201)

@app.get("/api/_exercises_for_select")
def api_exercises_for_select():
    # tiny helper endpoint to populate selects
    items = db.list_exercises(q=None, category=None)
    return JSONResponse([{ "id": e["id"], "name": e["name"] } for e in items])

@app.get("/api/_templates_for_select")
def api_templates_for_select():
    items = db.list_templates()
    return JSONResponse([{ "id": t["id"], "name": t["name"] } for t in items])

@app.post("/api/sessions/from_template")
async def api_create_session_from_template(request: Request):
    data = await request.json()
    template_id = data.get("template_id")
    date = (data.get("date") or "").strip()
    title = (data.get("title") or "").strip()
    notes = (data.get("notes") or "").strip()
    if not template_id or not date:
        raise HTTPException(status_code=400, detail={"error": "template_id and date are required"})
    try:
        s = db.create_session_from_template(template_id=int(template_id), date=date, title=title, notes=notes)
    except KeyError as e:
        raise HTTPException(status_code=404, detail={"error": str(e)})
    return JSONResponse(s, status_code=201)

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

# Tiny debug helpers
@app.get("/__debug/static-path")
def debug_static_path():
    return PlainTextResponse(str(STATIC_DIR))

@app.get("/__debug/templates-path")
def debug_templates_path():
    return PlainTextResponse(str(TEMPLATES_DIR))