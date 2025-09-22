// ===== config =====
const BASE = "http://127.0.0.1:8000";
const API = {
  exercises: `${BASE}/exercises`,
  templates: `${BASE}/templates`,
  sessions:  `${BASE}/sessions`,
};

async function fetchJSON(url, opts = {}) {
  const r = await fetch(url, { headers: { "Content-Type": "application/json" }, ...opts });
  if (!r.ok) {
    let msg = "";
    try { const j = await r.json(); msg = j.detail || JSON.stringify(j); } catch { msg = await r.text(); }
    throw new Error(`${r.status} ${msg}`);
  }
  return r.status === 204 ? null : r.json();
}
const $ = (sel) => document.querySelector(sel);
const byId = (id) => document.getElementById(id);

// ===== tabs =====
document.querySelectorAll(".tab").forEach(t => t.addEventListener("click", () => {
  document.querySelectorAll(".tab").forEach(x => x.classList.remove("active"));
  t.classList.add("active");
  const id = t.dataset.tab;
  ["ex","wo","se"].forEach(k => byId(`tab-${k}`).classList.toggle("hide", k !== id));
}));

// ===== exercises =====
async function loadExercisesTable() {
  const q = byId("ex-q").value.trim();
  const cat = byId("ex-cat-filter").value.trim();
  const qs = new URLSearchParams();
  if (q) qs.set("q", q);
  if (cat) qs.set("category", cat);
  const list = await fetchJSON(`${API.exercises}?${qs.toString()}`);
  const tbody = byId("ex-table").querySelector("tbody");
  tbody.innerHTML = "";
  list.forEach(e => {
    const tr = document.createElement("tr");
    tr.innerHTML = `<td>${e.id}</td><td>${e.name}</td><td>${e.category ?? ""}</td><td>${e.default_unit ?? ""}</td>`;
    tbody.appendChild(tr);
  });
  // refresh dropdowns used elsewhere
  fillExerciseOptions("#ti-exercise", list);
  fillExerciseOptions("#si-exercise", list);
}

function fillExerciseOptions(sel, list) {
  const el = document.querySelector(sel);
  el.innerHTML = "";
  list.forEach(e => {
    const o = document.createElement("option");
    o.value = e.id;
    o.textContent = `${e.name} (${e.category ?? "-"})`;
    o.dataset.category = e.category ?? "";
    el.appendChild(o);
  });
  if (sel === "#ti-exercise") updateTemplateItemFormMode(); // switch strength/cardio fields
}

async function addExercise() {
  const name = byId("ex-name").value.trim();
  if (!name) { alert("Name required"); return; }
  const payload = {
    name,
    category: byId("ex-category").value.trim() || null,
    default_unit: byId("ex-unit").value.trim() || null
  };
  await fetchJSON(API.exercises, { method: "POST", body: JSON.stringify(payload) });
  byId("ex-name").value = byId("ex-category").value = byId("ex-unit").value = "";
  await loadExercisesTable();
}

// ===== templates (workouts) =====
async function refreshTemplates() {
  const list = await fetchJSON(API.templates);
  const sel = byId("t-select");
  sel.innerHTML = "";
  list.forEach(t => {
    const o = document.createElement("option");
    o.value = t.id; o.textContent = `${t.id} — ${t.name}`;
    sel.appendChild(o);
  });
  byId("template-items-body").innerHTML = "";
  if (sel.value) await loadTemplateItems(parseInt(sel.value, 10));
}

async function createTemplate() {
  const name = byId("t-name").value.trim();
  if (!name) { alert("Workout name required"); return; }
  const notes = byId("t-notes").value.trim();
  await fetchJSON(API.templates, { method: "POST", body: JSON.stringify({ name, notes: notes || null }) });
  byId("t-name").value = ""; byId("t-notes").value = "";
  await refreshTemplates();
}

async function deleteTemplate() {
  const tid = byId("t-select").value; if (!tid) return;
  if (!confirm("Delete this workout and its items?")) return;
  await fetchJSON(`${API.templates}/${tid}`, { method:"DELETE" });
  await refreshTemplates();
}

function updateTemplateItemFormMode() {
  const sel = byId("ti-exercise");
  const opt = sel.options[sel.selectedIndex];
  const cat = (opt?.dataset.category || "").toLowerCase();
  const isCardio = cat.includes("cardio") || cat.includes("run") || cat.includes("bike");
  byId("ti-strength").classList.toggle("hide", isCardio);
  byId("ti-cardio").classList.toggle("hide", !isCardio);
}

async function addTemplateItem() {
  const tid = byId("t-select").value; if (!tid) { alert("Pick a workout"); return; }
  const opt = byId("ti-exercise").options[byId("ti-exercise").selectedIndex];
  const cat = (opt?.dataset.category || "").toLowerCase();
  const isCardio = cat.includes("cardio") || cat.includes("run") || cat.includes("bike");

  const payload = {
    exercise_id: parseInt(byId("ti-exercise").value, 10),
    sets: isCardio ? null : (byId("ti-sets").value ? parseInt(byId("ti-sets").value, 10) : null),
    reps: isCardio ? null : (byId("ti-reps").value ? parseInt(byId("ti-reps").value, 10) : null),
    weight_kg: isCardio ? null : (byId("ti-weight").value ? parseFloat(byId("ti-weight").value) : null),
    distance_km: isCardio ? (byId("ti-distance").value ? parseFloat(byId("ti-distance").value) : null) : null,
    notes: byId("ti-notes").value || null,
    order_index: (isCardio ? byId("ti-order-c").value : byId("ti-order").value) ? parseInt((isCardio ? byId("ti-order-c").value : byId("ti-order").value), 10) : null,
  };
  await fetchJSON(`${API.templates}/${tid}/items`, { method:"POST", body: JSON.stringify(payload) });
  // clear inputs
  ["ti-sets","ti-reps","ti-weight","ti-distance","ti-mins","ti-notes","ti-order","ti-order-c"].forEach(id => { const el = byId(id); if (el) el.value = ""; });
  await loadTemplateItems(parseInt(tid, 10));
}

async function loadTemplateItems(tid) {
  const rows = await fetchJSON(`${API.templates}/${tid}/items`);
  const tbody = byId("template-items-body"); tbody.innerHTML = "";
  rows.sort((a,b) => (a.order_index ?? 0) - (b.order_index ?? 0));
  rows.forEach(r => {
    const planned = (r.sets ?? "") && (r.reps ?? "")
      ? `${r.sets}×${r.reps}${r.weight_kg ? ` @ ${r.weight_kg}kg` : ""}`
      : (r.distance_km ? `${r.distance_km} km` : "");
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${r.id}</td>
      <td>${r.order_index ?? ""}</td>
      <td>${r.exercise_name}</td>
      <td>${planned}</td>
      <td>${r.notes ?? ""}</td>
      <td class="right"><button class="btn-del-ti" data-id="${r.id}" data-tid="${tid}">Delete</button></td>
    `;
    tbody.appendChild(tr);
  });
  tbody.querySelectorAll(".btn-del-ti").forEach(btn => {
    btn.addEventListener("click", async () => {
      const id = btn.dataset.id, t = btn.dataset.tid;
      if (!confirm(`Delete item #${id}?`)) return;
      await fetchJSON(`${API.templates}/${t}/items/${id}`, { method:"DELETE" });
      await loadTemplateItems(parseInt(t,10));
    });
  });
}

// make session from template
async function makeSessionFromTemplate() {
  const tid = byId("t-select").value; if (!tid) { alert("Pick a workout"); return; }
  const d = byId("ms-date").value; if (!d) { alert("Pick a date"); return; }
  const title = byId("ms-title").value.trim();
  const notes = ""; // keep simple for now
  const url = new URL(`${API.templates}/${tid}/make-session`);
  url.searchParams.set("date", d);
  if (title) url.searchParams.set("title", title);
  if (notes) url.searchParams.set("notes", notes);
  await fetchJSON(url.toString(), { method:"POST" });
  alert("Session created.");
  await refreshSessions();
}

// ===== sessions =====
async function refreshSessions() {
  const list = await fetchJSON(API.sessions);
  const sel = byId("s-select"); sel.innerHTML = "";
  list.forEach(s => {
    const o = document.createElement("option");
    o.value = s.id; o.textContent = `${s.id} — ${s.date}${s.title ? " — " + s.title : ""}`;
    sel.appendChild(o);
  });
  byId("items-tbody").innerHTML = "";
  if (sel.value) await loadSessionItems(parseInt(sel.value, 10));
}

async function createSession() {
  const date = byId("s-date").value; if (!date) { alert("Pick a date"); return; }
  const payload = { date, title: byId("s-title").value || null, notes: byId("s-notes").value || null };
  await fetchJSON(API.sessions, { method:"POST", body: JSON.stringify(payload) });
  await refreshSessions();
}

async function loadSessionItems(sessionId) {
  const items = await fetchJSON(`${API.sessions}/${sessionId}/items`);
  const tbody = byId("items-tbody"); tbody.innerHTML = "";
  items.sort((a,b) => (a.order_index ?? 0) - (b.order_index ?? 0));
  items.forEach(it => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${it.id}</td>
      <td>${it.order_index ?? ""}</td>
      <td>${it.exercise_name}</td>
      <td>${it.notes ?? ""}</td>
      <td class="right"><button data-id="${it.id}" data-session="${it.session_id}" class="btn-del-item">Delete</button></td>
    `;
    tbody.appendChild(tr);
  });
  tbody.querySelectorAll(".btn-del-item").forEach(btn => {
    btn.addEventListener("click", async () => {
      const itemId = parseInt(btn.dataset.id, 10);
      const sessionId = parseInt(btn.dataset.session, 10);
      if (!confirm(`Delete item ${itemId}?`)) return;
      await fetchJSON(`${API.sessions}/${sessionId}/items/${itemId}`, { method:"DELETE" });
      await loadSessionItems(sessionId);
    });
  });
}

async function addSessionItem() {
  const sid = byId("s-select").value; if (!sid) { alert("Pick a session"); return; }
  const payload = {
    exercise_id: parseInt(byId("si-exercise").value, 10),
    notes: byId("si-notes").value || null,
    order_index: byId("si-order").value ? parseInt(byId("si-order").value, 10) : null,
  };
  await fetchJSON(`${API.sessions}/${sid}/items`, { method:"POST", body: JSON.stringify(payload) });
  byId("si-notes").value = ""; byId("si-order").value = "";
  await loadSessionItems(parseInt(sid,10));
}

// ===== init wiring =====
function wire() {
  // exercises
  byId("btn-add-exercise").addEventListener("click", addExercise);
  byId("ex-q").addEventListener("input", debounce(loadExercisesTable, 200));
  byId("ex-cat-filter").addEventListener("input", debounce(loadExercisesTable, 200));

  // templates
  byId("btn-create-template").addEventListener("click", createTemplate);
  byId("btn-refresh-templates").addEventListener("click", refreshTemplates);
  byId("btn-delete-template").addEventListener("click", deleteTemplate);
  byId("btn-add-template-item").addEventListener("click", addTemplateItem);
  byId("t-select").addEventListener("change", (e) => loadTemplateItems(parseInt(e.target.value, 10)));
  byId("ti-exercise").addEventListener("change", updateTemplateItemFormMode);
  byId("btn-make-session").addEventListener("click", makeSessionFromTemplate);

  // sessions
  byId("btn-create-session").addEventListener("click", createSession);
  byId("btn-refresh-sessions").addEventListener("click", refreshSessions);
  byId("btn-add-item").addEventListener("click", addSessionItem);
  byId("s-select").addEventListener("change", (e) => loadSessionItems(parseInt(e.target.value, 10)));
}

function debounce(fn, wait=200) {
  let t; return (...args) => { clearTimeout(t); t = setTimeout(() => fn(...args), wait); };
}

async function init() {
  wire();
  const today = new Date().toISOString().slice(0,10);
  byId("s-date").value = today; byId("ms-date").value = today;
  await loadExercisesTable();
  await refreshTemplates();
  await refreshSessions();
}

init();