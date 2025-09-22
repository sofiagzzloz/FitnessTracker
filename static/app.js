const $ = (sel) => document.querySelector(sel);

const BASE = "http://127.0.0.1:8000";
const API = {
  exercises: `${BASE}/exercises`,
  workouts:  `${BASE}/workouts`,   // legacy v1; might delete later 
  sessions:  `${BASE}/sessions`,
  templates: `${BASE}/templates`,
};

async function fetchJSON(url, opts = {}) {
  const r = await fetch(url, { headers: { "Content-Type": "application/json" }, ...opts });
  if (!r.ok) throw new Error(await r.text());
  return r.status === 204 ? null : r.json();
}

async function loadExercises() {
  const items = await fetchJSON(API.exercises);
  const sel = $("#exercise");
  sel.innerHTML = "";
  items.forEach(ex => {
    const opt = document.createElement("option");
    opt.value = ex.id;
    opt.textContent = `${ex.name} ${ex.category ? `(${ex.category})`: ""}`;
    sel.appendChild(opt);
  });
}

function qs(params) {
  const u = new URLSearchParams();
  Object.entries(params).forEach(([k,v]) => { if (v) u.set(k, v); });
  const s = u.toString();
  return s ? ("?" + s) : "";
}

async function loadWorkouts() {
  const params = {
    on_date: $("#f-on").value,
    start_date: $("#f-start").value,
    end_date: $("#f-end").value,
    exercise: $("#f-exercise").value.trim()
  };
  const items = await fetchJSON(API.workouts + qs(params));
  const tbody = $("#workouts-table tbody");
  tbody.innerHTML = "";
  items.forEach(w => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${w.id}</td>
      <td>${w.date}</td>
      <td>${w.exercise_name}</td>
      <td>${w.sets ?? ""}</td>
      <td>${w.reps ?? ""}</td>
      <td>${w.weight_kg ?? ""}</td>
      <td>${w.distance_km ?? ""}</td>
      <td>${w.notes ?? ""}</td>
      <td><button data-id="${w.id}" class="del">Delete</button></td>
    `;
    tbody.appendChild(tr);
  });
}

async function createWorkout(e) {
  e.preventDefault();
  const body = {
    date: $("#date").value,
    exercise_id: parseInt($("#exercise").value, 10),
  };
  // only send fields that have values (so we don't zero-out)
  const sets = $("#sets").value; if (sets !== "") body.sets = parseInt(sets, 10);
  const reps = $("#reps").value; if (reps !== "") body.reps = parseInt(reps, 10);
  const weight = $("#weight_kg").value; if (weight !== "") body.weight_kg = parseFloat(weight);
  const dist = $("#distance_km").value; if (dist !== "") body.distance_km = parseFloat(dist);
  const notes = $("#notes").value; if (notes.trim() !== "") body.notes = notes.trim();

  try {
    await fetchJSON(API.workouts, { method: "POST", body: JSON.stringify(body) });
    $("#create-msg").textContent = "Created!";
    (e.target).reset();
    await loadWorkouts();
  } catch (err) {
    $("#create-msg").textContent = "Error: " + err.message;
  }
}

async function onTableClick(e) {
  if (e.target.classList.contains("del")) {
    const id = e.target.getAttribute("data-id");
    if (!confirm(`Delete workout #${id}?`)) return;
    try {
      await fetchJSON(`${API.workouts}/${id}`, { method: "DELETE" });
      await loadWorkouts();
    } catch (err) {
      alert("Delete failed: " + err.message);
    }
  }
}

function toggleExerciseQuick(show) {
  $("#exercise-quick").hidden = !show;
}

async function saveExercise() {
  const body = {
    name: $("#ex-name").value.trim(),
    category: $("#ex-category").value.trim() || undefined,
    default_unit: $("#ex-unit").value.trim() || undefined
  };
  if (!body.name) { $("#ex-msg").textContent = "Name required."; return; }
  try {
    await fetchJSON(API.exercises, { method: "POST", body: JSON.stringify(body) });
    $("#ex-msg").textContent = "Saved!";
    $("#ex-name").value = $("#ex-category").value = $("#ex-unit").value = "";
    toggleExerciseQuick(false);
    await loadExercises();
  } catch (err) {
    $("#ex-msg").textContent = "Error: " + err.message;
  }
}

function wireEvents() {
  $("#create-form").addEventListener("submit", createWorkout);
  $("#workouts-table").addEventListener("click", onTableClick);
  $("#add-exercise").addEventListener("click", () => toggleExerciseQuick(true));
  $("#cancel-ex").addEventListener("click", () => toggleExerciseQuick(false));
  $("#save-ex").addEventListener("click", saveExercise);
  $("#apply-filters").addEventListener("click", loadWorkouts);
  $("#clear-filters").addEventListener("click", async () => {
    $("#f-on").value = $("#f-start").value = $("#f-end").value = $("#f-exercise").value = "";
    await loadWorkouts();
  });
}

async function init() {
  wireEvents();
  // default date = today
  $("#date").value = new Date().toISOString().slice(0,10);
  await loadExercises();
  await loadWorkouts();
}

// ------- helpers -------
function val(id) { return document.getElementById(id).value; }
function setOptions(selectEl, arr, toLabel = x => x.label, toValue = x => x.value) {
  selectEl.innerHTML = "";
  arr.forEach(opt => {
    const o = document.createElement("option");
    o.textContent = toLabel(opt);
    o.value = toValue(opt);
    selectEl.appendChild(o);
  });
}

// ------- load exercises for dropdown -------
async function loadExercisesForItems() {
  const res = await fetch(`${API}/exercises?limit=200`);
  const data = await res.json();
  const options = data.map(e => ({ label: `${e.name} (${e.category ?? "-"})`, value: e.id }));
  setOptions(document.getElementById("si-exercise"), options);
}

// ------- sessions: list / refresh -------
async function refreshSessionsDropdown() {
  const res = await fetch(`${API}/sessions`);
  const sessions = await res.json();
  const options = sessions.map(s => ({
    label: `${s.id} — ${s.date}${s.title ? " — " + s.title : ""}`,
    value: s.id
  }));
  const sel = document.getElementById("s-select");
  setOptions(sel, options);
  // if there is at least one session, load its items
  if (sel.value) {
    await loadSessionItems(parseInt(sel.value, 10));
  } else {
    document.getElementById("items-tbody").innerHTML = "";
  }
}

// ------- create session -------
async function createSession() {
  const payload = {
    date: val("s-date"),
    title: val("s-title") || null,
    notes: val("s-notes") || null
  };
  if (!payload.date) {
    alert("Please pick a date");
    return;
  }
  const res = await fetch(`${API}/sessions`, {
    method: "POST",
    headers: {"content-type":"application/json"},
    body: JSON.stringify(payload)
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    alert(`Failed to create session: ${res.status} ${err.detail ?? ""}`);
    return;
  }
  await refreshSessionsDropdown();
  // preselect the newest one (first option from refresh is latest due to order)
  alert("Session created");
}

// ------- list items for selected session -------
// (MVP: we don’t have a GET /sessions/{id}/items endpoint, so we’ll fetch the
// session (for existence) and then call a tiny helper endpoint you can add later.
// For now, we’ll just call /workouts as a placeholder if needed. The real way is
// to expose /sessions/{id} returning items. For MVP, we’ll keep items client-side
// after adding. Simpler: call a tiny /sessions/{id} GET and maintain items locally.)
let _lastItemsCache = []; // simple cache after adding

async function loadSessionItems(sessionId) {
  renderItemsTable(_lastItemsCache.filter(it => it.session_id === sessionId));
}

function renderItemsTable(items) {
  const tbody = document.getElementById("items-tbody");
  tbody.innerHTML = "";
  items.sort((a,b) => (a.order_index ?? 0) - (b.order_index ?? 0));
  for (const it of items) {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${it.id}</td>
      <td>${it.order_index ?? ""}</td>
      <td>${it.exercise_name}</td>
      <td>${it.notes ?? ""}</td>
      <td><button data-id="${it.id}" data-session="${it.session_id}" class="btn-del-item">Delete</button></td>
    `;
    tbody.appendChild(tr);
  }

  // wire delete buttons
  document.querySelectorAll(".btn-del-item").forEach(btn => {
    btn.addEventListener("click", async () => {
      const itemId = parseInt(btn.getAttribute("data-id"), 10);
      const sessionId = parseInt(btn.getAttribute("data-session"), 10);
      const ok = confirm(`Delete item ${itemId}?`);
      if (!ok) return;
      const res = await fetch(`${API}/sessions/${sessionId}/items/${itemId}`, { method: "DELETE" });
      if (res.status !== 204) {
        const err = await res.json().catch(() => ({}));
        alert(`Failed to delete: ${res.status} ${err.detail ?? ""}`);
        return;
      }
      // remove from cache + re-render
      _lastItemsCache = _lastItemsCache.filter(x => x.id !== itemId);
      await loadSessionItems(sessionId);
    });
  });
}

// ------- add item to selected session -------
async function addItemToSession() {
  const sessionIdStr = document.getElementById("s-select").value;
  if (!sessionIdStr) {
    alert("Select a session first");
    return;
  }
  const sessionId = parseInt(sessionIdStr, 10);
  const payload = {
    exercise_id: parseInt(document.getElementById("si-exercise").value, 10),
    notes: document.getElementById("si-notes").value || null,
    order_index: document.getElementById("si-order").value ? parseInt(document.getElementById("si-order").value, 10) : null
  };
  const res = await fetch(`${API}/sessions/${sessionId}/items`, {
    method: "POST",
    headers: {"content-type":"application/json"},
    body: JSON.stringify(payload)
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    alert(`Failed to add item: ${res.status} ${err.detail ?? ""}`);
    return;
  }
  const item = await res.json();
  // keep a simple client-side cache; later replace with real GET items endpoint
  _lastItemsCache = _lastItemsCache.filter(x => x.session_id !== sessionId).concat(item);
  await loadSessionItems(sessionId);
  // clear notes/order inputs for quick next add
  document.getElementById("si-notes").value = "";
  document.getElementById("si-order").value = "";
}

// ------- wire up on load -------
window.addEventListener("DOMContentLoaded", async () => {
  document.getElementById("btn-create-session").addEventListener("click", createSession);
  document.getElementById("btn-refresh-sessions").addEventListener("click", refreshSessionsDropdown);
  document.getElementById("btn-add-item").addEventListener("click", addItemToSession);
  document.getElementById("s-select").addEventListener("change", async (e) => {
    await loadSessionItems(parseInt(e.target.value, 10));
  });

  await loadExercisesForItems();
  await refreshSessionsDropdown();
});

init();