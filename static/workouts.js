// ========== tiny DOM helpers ==========
function el(id) { return document.getElementById(id); }
function h(tag, attrs = {}, ...kids) {
  const n = document.createElement(tag);
  Object.entries(attrs || {}).forEach(([k, v]) => {
    if (k === "class") n.className = v;
    else if (k === "text") n.textContent = v;
    else n.setAttribute(k, v);
  });
  kids.forEach(k => n.appendChild(typeof k === "string" ? document.createTextNode(k) : k));
  return n;
}

// ========== state ==========
const state = {
  workouts: [],
  selectedId: null,
  items: [],
  exercises: [],
};

// map exerciseId -> category for quick lookup
const exCategoryById = new Map();

// track whether current selection is cardio
let isCardio = false;

function setPlannerForCardio(on) {
  isCardio = !!on;

  // Inputs
  const inSets   = el('item-sets');
  const inReps   = el('item-reps');
  const inWeight = el('item-weight');

  // Labels (if you added the optional IDs)
  const lblSets   = document.getElementById('lbl-sets');
  const lblReps   = document.getElementById('lbl-reps');
  const lblWeight = document.getElementById('lbl-weight');

  if (on) {
    // Cardio mode
    lblSets   && (lblSets.textContent   = 'Minutes');
    lblReps   && (lblReps.textContent   = 'Distance');
    lblWeight && (lblWeight.textContent = 'Pace / HR (optional)');

    inSets.type = 'number';   inSets.min = '0';  inSets.placeholder = '30';
    inReps.type = 'number';   inReps.min = '0';  inReps.step = '0.1'; inReps.placeholder = '5 (km/mi)';
    // use "weight" box as a free text note in cardio
    inWeight.type = 'text';   inWeight.placeholder = 'e.g. 5:30/km or HR 150';

  } else {
    // Strength mode (original)
    lblSets   && (lblSets.textContent   = 'Sets');
    lblReps   && (lblReps.textContent   = 'Reps');
    lblWeight && (lblWeight.textContent = 'Weight');

    inSets.type = 'number';   inSets.min = '1';  inSets.placeholder = '3';
    inReps.type = 'number';   inReps.min = '1';  inReps.placeholder = '10';
    inWeight.type = 'number'; inWeight.step = '0.5'; inWeight.placeholder = 'kg/lb';
  }
}
// ========== API helpers ==========
async function apiListWorkouts(q) {
  const res = await fetch("/api/workouts" + (q ? `?q=${encodeURIComponent(q)}` : ""));
  return res.ok ? res.json() : [];
}
async function apiCreateWorkout(name) {
  const res = await fetch("/api/workouts", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name })
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}
async function apiDeleteWorkout(id) {
  const res = await fetch(`/api/workouts/${id}`, { method: "DELETE" });
  if (!res.ok) throw new Error(await res.text());
}
async function apiListItems(tid) {
  const res = await fetch(`/api/workouts/${tid}/items`);
  return res.ok ? res.json() : [];
}
async function apiAddItem(tid, payload) {
  const res = await fetch(`/api/workouts/${tid}/items`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}
async function apiDeleteItem(itemId) {
  const res = await fetch(`/api/workouts/items/${itemId}`, { method: "DELETE" });
  if (!res.ok) throw new Error(await res.text());
}
async function apiListExercises() {
  const cap = 200;
  let res = await fetch(`/api/exercises?limit=${cap}`);
  if (res.ok) return res.json();
  if (res.status === 422) {
    res = await fetch("/api/exercises?limit=100");
    return res.ok ? res.json() : [];
  }
  const txt = await res.text().catch(() => "");
  console.error("[workouts] /api/exercises failed:", res.status, txt);
  return [];
}
async function apiTemplateMuscles(tid) {
  const res = await fetch(`/api/workouts/${tid}/muscles`);
  if (!res.ok) return { primary: {}, secondary: {} };
  return res.json();
}

async function apiPatchItem(itemId, patch) {
  const res = await fetch(`/api/workouts/items/${itemId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(patch),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

// ========== UI: workouts list / items table ==========
function renderWorkoutList() {
  const box = el("wo-list");
  box.innerHTML = "";
  if (!state.workouts.length) {
    box.innerHTML = '<p class="muted">No workouts yet.</p>';
    return;
  }
  state.workouts.forEach(w => {
    const a = h("button", { class: "tab", style: "width:100%; text-align:left" });
    a.textContent = w.name;
    a.addEventListener("click", () => selectWorkout(w.id));
    if (w.id === state.selectedId) a.classList.add("active");
    box.appendChild(a);
  });
}

function setEditorEnabled(enabled) {
  el("wo-empty").style.display = enabled ? "none" : "";
  el("wo-editor").style.display = enabled ? "" : "none";
  el("wo-delete").disabled = !enabled;
}

function renderItems() {
  const tb = document.querySelector("#items-table tbody");
  tb.innerHTML = "";
  if (!state.items.length) {
    tb.innerHTML = '<tr><td colspan="4" class="muted">No items yet.</td></tr>';
    return;
  }

  const exMap = new Map(state.exercises.map(e => [e.id, e]));

  state.items.forEach((it, idx) => {
    const tr = document.createElement("tr");
    tr.dataset.itemId = it.id;

    const tdIdx = h("td", {}, String(idx + 1));
    const tdEx  = h("td", {}, exMap.get(it.exercise_id)?.name || it.exercise_id);
    const tdPln = h("td", {}, planText(it));
    const tdAct = h("td", { class: "right" });

    // view-mode actions: Edit + Remove
    const editBtn = h("button", { class: "btn-small", text: "Edit" });
    const delBtn  = h("button", { class: "btn-small danger", text: "Remove" });

    editBtn.addEventListener("click", () => enterEditRow(tr, it));
    delBtn.addEventListener("click", async () => {
      if (!confirm("Remove item?")) return;
      try {
        await apiDeleteItem(it.id);
        await refreshItems();
      } catch (e) { alert(e.message || "Delete failed"); }
    });

    tdAct.appendChild(editBtn);
    tdAct.appendChild(document.createTextNode(" "));
    tdAct.appendChild(delBtn);

    tr.appendChild(tdIdx);
    tr.appendChild(tdEx);
    tr.appendChild(tdPln);
    tr.appendChild(tdAct);

    tb.appendChild(tr);
  });
}

function enterEditRow(tr, it) {
  const tdPln = tr.children[2];
  const tdAct = tr.children[3];

  // build inputs prefilled from item
  const inSets = h("input", { type: "number", min: "0", class: "input", style: "width:80px", value: it.planned_sets ?? "" });
  const inReps = h("input", { type: "number", min: "0", class: "input", style: "width:80px", value: it.planned_reps ?? "" });
  const inWgt  = h("input", { type: "number", step: "0.5", class: "input", style: "width:120px", value: it.planned_weight ?? "" });

  // render mini form inside the Planned cell: Sets | Reps | Weight
  tdPln.innerHTML = "";
  tdPln.append(
    wrapMiniField("Sets", inSets),
    " ",
    wrapMiniField("Reps", inReps),
    " ",
    wrapMiniField("Weight", inWgt)
  );

  // actions: Save / Cancel / Remove
  const saveBtn   = h("button", { class: "btn-small", text: "Save" });
  const cancelBtn = h("button", { class: "btn-small", text: "Cancel" });
  const delBtn    = h("button", { class: "btn-small danger", text: "Remove" });

  tdAct.innerHTML = "";
  tdAct.append(saveBtn, document.createTextNode(" "), cancelBtn, document.createTextNode(" "), delBtn);
  tdAct.classList.add("right");

  // Remove (same as view)
  delBtn.addEventListener("click", async () => {
    if (!confirm("Remove item?")) return;
    try { await apiDeleteItem(it.id); await refreshItems(); }
    catch (e) { alert(e.message || "Delete failed"); }
  });

  // Save → PATCH
  saveBtn.addEventListener("click", async () => {
    try {
      await apiPatchItem(it.id, {
        planned_sets:   toInt(inSets.value),
        planned_reps:   toInt(inReps.value),
        planned_weight: toFloat(inWgt.value),
      });
      await refreshItems();
    } catch (e) {
      alert(e.message || "Update failed");
    }
  });

  // Cancel → go back to view mode
  cancelBtn.addEventListener("click", () => {
    tdPln.textContent = planText(it);
    tdAct.innerHTML = "";
    const editBtn = h("button", { class: "btn-small", text: "Edit" });
    const delBtn2 = h("button", { class: "btn-small danger", text: "Remove" });
    editBtn.addEventListener("click", () => enterEditRow(tr, it));
    delBtn2.addEventListener("click", async () => {
      if (!confirm("Remove item?")) return;
      try { await apiDeleteItem(it.id); await refreshItems(); }
      catch (e) { alert(e.message || "Delete failed"); }
    });
    tdAct.append(editBtn, document.createTextNode(" "), delBtn2);
  });

  // Enter saves
  [inSets, inReps, inWgt].forEach(inp => inp.addEventListener("keydown", e => {
    if (e.key === "Enter") saveBtn.click();
  }));

  inSets.focus();
}

// tiny UI helper to label small inputs inside the Planned cell
function wrapMiniField(lbl, inputEl){
  const box = document.createElement("span");
  box.style.display = "inline-flex";
  box.style.alignItems = "center";
  box.style.gap = "6px";
  const small = document.createElement("small");
  small.className = "hint";
  small.textContent = lbl;
  box.append(small, inputEl);
  return box;
}

function planText(it) {
  // figure out the exercise category for this item
  const cat = exCategoryById.get(it.exercise_id) || '';

  if (cat === 'cardio') {
    const mins = it.planned_sets != null ? `${it.planned_sets}m` : '';
    const dist = it.planned_reps != null ? `${it.planned_reps}${''}` : ''; // unit free; user knows their unit
    const pace = (it.notes && it.notes.trim()) ? ` — ${it.notes.trim()}` : '';
    const parts = [mins, dist].filter(Boolean).join(' ');
    return parts || pace || '—';
  }

  // strength (original)
  const parts = [];
  if (it.planned_sets) parts.push(`${it.planned_sets}x`);
  if (it.planned_reps) parts.push(`${it.planned_reps}`);
  if (it.planned_weight) parts.push(`${it.planned_weight}`);
  if (!parts.length) return "—";
  return parts.join(" ");
}

// ========== MUSCLE MAP (front/back canvases with heat gradient) ==========

// Coordinates (percent) with optional scale "s"
const FRONT_POS = {
  chest:        [{x:50, y:21}],
  front_delts:  [{x:31, y:19},{x:69, y:19}],
  side_delts:   [{x:24, y:20},{x:76, y:20}],
  biceps:       [{x:23, y:31, s:.95},{x:77, y:31, s:.95}],
  triceps:      [{x:23, y:31, s:.95},{x:77, y:31, s:.95}],
  abs:          [{x:50, y:35, s:.95}],
  quads:        [{x:41, y:63, s:1.18},{x:59, y:63, s:1.18}],
  calves:       [{x:39, y:80, s:.95},{x:61, y:80, s:.95}],
};

const BACK_POS = {
  traps:        [{x:35, y:16}, {x:50, y:16}],
  lats:         [{x:35, y:28, s:1.1},{x:55, y:28, s:1.1}],
  lower_back:   [{x:44, y:40}],
  glutes:       [{x:44, y:48, s:1.15}],
  hams:         [{x:39, y:57, s:1.1},{x:51, y:57, s:1.1}],
  calves:       [{x:33, y:80, s:.95},{x:58, y:80, s:.95}],
};

// Heat colors (red primary, yellow secondary)
const HEAT = {
  primary:   { inner: "rgba(255, 77, 79, 0.95)",  mid: "rgba(255, 77, 79, 0.35)",  outer: "rgba(255, 77, 79, 0.0)" },
  secondary: { inner: "rgba(255, 193, 7, 0.85)",  mid: "rgba(255, 193, 7, 0.28)", outer: "rgba(255, 193, 7, 0.0)" }
};

// Heuristic fallbacks when DB has no links
function normName(s) { return (s || "").toLowerCase(); }
function guessMusclesByName(name) {
  const n = normName(name);

  // — Legs —
  if (/(^|[^a-z])leg\s*press|hack\s*squat|smith\s*squat|front\s*squat|back\s*squat|goblet\s*squat|split\s*squat/.test(n))
    return { primary: ["quads", "glutes"], secondary: ["hams", "calves", "abs"] };

  if (/leg\s*extension/.test(n))
    return { primary: ["quads"], secondary: ["abs"] };

  if (/leg\s*curl|hamstring\s*curl/.test(n))
    return { primary: ["hams"], secondary: ["glutes", "calves"] };

  if (/calf\s*(raise|press)/.test(n))
    return { primary: ["calves"], secondary: ["hams"] };

  if (/hyperextension|back\s*extension/.test(n))
    return { primary: ["lower_back"], secondary: ["glutes", "hams"] };

  // — Chest / Shoulders / Arms —
  if (/bench|chest\s*press|push[- ]?up/.test(n))
    return { primary: ["chest"], secondary: ["front_delts", "triceps", "abs"] };

  if (/overhead\s*press|shoulder\s*press|military\s*press/.test(n))
    return { primary: ["front_delts", "side_delts"], secondary: ["triceps", "traps"] };

  if (/lateral\s*raise/.test(n))
    return { primary: ["side_delts"], secondary: [] };

  if (/\bbiceps?\b.*curl|(^|[^a-z])curl\b/.test(n))
    return { primary: ["biceps"], secondary: [] };

  if (/triceps?.*(extension|pushdown)|skull\s*crusher/.test(n))
    return { primary: ["triceps"], secondary: [] };

  // — Back —
  if (/row|pulldown|pull[- ]?up|chin[- ]?up/.test(n))
    return { primary: ["lats"], secondary: ["biceps", "traps"] };

  if (/deadlift/.test(n))
    return { primary: ["hams", "glutes", "lower_back"], secondary: ["traps", "lats"] };

  // — Core —
  if (/\babs?\b|crunch|sit[- ]?up|plank/.test(n))
    return { primary: ["abs"], secondary: [] };

  return { primary: [], secondary: [] };
}

function buildFallbackSummary(items, exercises) {
  const exMap = new Map(exercises.map(e => [e.id, e]));
  const primary = {}, secondary = {};
  for (const it of items) {
    const ex = exMap.get(it.exercise_id);
    if (!ex) continue;
    const g = guessMusclesByName(ex.name);
    g.primary.forEach(sl => primary[sl] = (primary[sl] || 0) + 1);
    g.secondary.forEach(sl => secondary[sl] = (secondary[sl] || 0) + 1);
  }
  return { primary, secondary };
}

function mergeSummaries(server, fallback) {
  const merged = {
    primary:   { ...fallback.primary,   ...(server.primary   || {}) },
    secondary: { ...fallback.secondary, ...(server.secondary || {}) },
  };
  // don’t show a muscle as secondary if it’s counted as primary
  Object.keys(merged.primary).forEach(k => { delete merged.secondary[k]; });
  return merged;
}

// canvas utils
let _lastSummary = null;

function getCtx(which) { // 'front' | 'back'
  const canvas = document.getElementById(`${which}-canvas`);
  const img    = document.getElementById(`body-${which}`);
  if (!canvas || !img) return null;

  const rect = img.getBoundingClientRect();
  const w = Math.max(1, Math.round(rect.width));
  const h = Math.max(1, Math.round(rect.height));
  if (canvas.width !== w || canvas.height !== h) {
    canvas.width = w; canvas.height = h;
  }
  const ctx = canvas.getContext("2d");
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  return ctx;
}

function levelFromCount(c, max) {
  if (!max) return 1;
  const r = c / max;
  if (r >= 0.9) return 4;
  if (r >= 0.6) return 3;
  if (r >= 0.3) return 2;
  return 1;
}

function drawSpot(ctx, xPct, yPct, level, role, scale = 1) {
  if (!ctx) return;
  const w = ctx.canvas.width, h = ctx.canvas.height;
  const x = (xPct / 100) * w;
  const y = (yPct / 100) * h;

  const base = Math.min(w, h) * 0.10; // ~10% of shorter side
  const r = base * (0.8 + 0.2 * level) * (scale || 1);

  const grad = ctx.createRadialGradient(x, y, r * 0.05, x, y, r);
  const col = HEAT[role] || HEAT.primary;
  grad.addColorStop(0, col.inner);
  grad.addColorStop(0.5, col.mid);
  grad.addColorStop(1, col.outer);

  ctx.beginPath();
  ctx.fillStyle = grad;
  ctx.arc(x, y, r, 0, Math.PI * 2);
  ctx.fill();
}

function pretty(slug) { return slug.replace(/_/g, " "); }

function applyMapColors(summary) {
  _lastSummary = summary;

  const fctx = getCtx("front");
  const bctx = getCtx("back");
  if (fctx) fctx.clearRect(0, 0, fctx.canvas.width, fctx.canvas.height);
  if (bctx) bctx.clearRect(0, 0, bctx.canvas.width, bctx.canvas.height);

  const prim = summary?.primary || {};
  const sec  = summary?.secondary || {};

  const cp = el("chips-primary"); cp.innerHTML = "";
  const cs = el("chips-secondary"); cs.innerHTML = "";
  const note = el("map-note");

  const pKeys = Object.keys(prim);
  const sKeys = Object.keys(sec);
  const maxP = Math.max(0, ...Object.values(prim));
  const maxS = Math.max(0, ...Object.values(sec));

  pKeys.forEach(slug => {
    const lvl = levelFromCount(prim[slug], maxP);
    (FRONT_POS[slug] || []).forEach(hp => drawSpot(fctx, hp.x, hp.y, lvl, "primary", hp.s));
    (BACK_POS[slug]  || []).forEach(hp => drawSpot(bctx, hp.x, hp.y, lvl, "primary", hp.s));
    cp.appendChild(h("span", { class: "chip" }, `${pretty(slug)} ×${prim[slug]}`));
  });

  sKeys.forEach(slug => {
    if (prim[slug]) return; // don't double paint
    const lvl = levelFromCount(sec[slug], maxS);
    (FRONT_POS[slug] || []).forEach(hp => drawSpot(fctx, hp.x, hp.y, lvl, "secondary", hp.s));
    (BACK_POS[slug]  || []).forEach(hp => drawSpot(bctx, hp.x, hp.y, lvl, "secondary", hp.s));
    cs.appendChild(h("span", { class: "chip" }, `${pretty(slug)} ×${sec[slug]}`));
  });

  note.textContent = (pKeys.length || sKeys.length) ? "" : "Add items to see muscles.";
}

// Redraw when window resizes so canvases match images
window.addEventListener("resize", () => {
  if (!_lastSummary) return;
  // ensure images laid out before sizing canvases
  const imgs = [...document.querySelectorAll(".bodyimg img")];
  Promise.all(imgs.map(img => (img.complete ? Promise.resolve() : new Promise(r => img.onload = r))))
    .then(() => applyMapColors(_lastSummary));
});

// ========== actions ==========
async function selectWorkout(id) {
  state.selectedId = id;
  const w = state.workouts.find(x => x.id === id);
  el("wo-title").textContent = w ? w.name : "Workout";
  setEditorEnabled(true);
  renderWorkoutList();

  // wait until body images have a layout size, then render
  const imgs = [...document.querySelectorAll(".bodyimg img")];
  await Promise.all(imgs.map(img => (img.complete ? Promise.resolve() : new Promise(r => img.onload = r))));
  await refreshItems();
}

async function refreshItems(){
  if (!state.selectedId) return;

  state.items = await apiListItems(state.selectedId);
  renderItems();

  try {
    const serverSummary   = await apiTemplateMuscles(state.selectedId);
    const fallbackSummary = buildFallbackSummary(state.items, state.exercises);

    const hasServerData =
      (serverSummary?.primary   && Object.keys(serverSummary.primary).length) ||
      (serverSummary?.secondary && Object.keys(serverSummary.secondary).length);

    const summary = hasServerData
      ? mergeSummaries(serverSummary, fallbackSummary)  // combine: server > fallback
      : fallbackSummary;                                 // only fallback

    applyMapColors(summary);
  } catch (e) {
    console.error('[workouts] muscle map load failed:', e);
    const fallback = buildFallbackSummary(state.items, state.exercises);
    applyMapColors(fallback);
  }
}

async function refreshWorkouts() {
  state.workouts = await apiListWorkouts(el("wo-filter").value.trim());
  renderWorkoutList();
}

async function initExercisesSelect() {
  try {
    state.exercises = await apiListExercises();

    // build category map
    exCategoryById.clear();
    state.exercises.forEach(ex => {
      if (ex && ex.id) exCategoryById.set(ex.id, (ex.category || '').toLowerCase());
    });

    const sel = el("item-ex-select");
    if (!sel) { console.warn("[workouts] missing #item-ex-select"); return; }

    sel.innerHTML = '<option value="">Choose…</option>';
    if (!state.exercises.length) {
      const opt = document.createElement("option");
      opt.value = "";
      opt.textContent = "No local exercises yet — import or add some on the Exercises page";
      sel.appendChild(opt);
      return;
    }
    state.exercises.forEach(ex => {
      const opt = document.createElement("option");
      opt.value = ex.id;
      opt.textContent = ex.name;
      sel.appendChild(opt);
    });

    // swap UI on change
    sel.addEventListener('change', () => {
      const id = Number(sel.value);
      const cat = exCategoryById.get(id) || '';
      setPlannerForCardio(cat === 'cardio');
    });

  } catch (e) {
    console.error("[workouts] failed to load exercises", e);
    alert(e.message || "Could not load exercises list.");
  }
}

// ========== wiring ==========
document.addEventListener("DOMContentLoaded", async () => {
  // create
  el("wo-create").addEventListener("click", async () => {
    const name = (el("wo-new-name").value || "").trim();
    if (!name) return alert("Name required");
    try {
      const w = await apiCreateWorkout(name);
      el("wo-new-name").value = "";
      await refreshWorkouts();
      await selectWorkout(w.id);
    } catch (e) { alert(e.message || "Create failed"); }
  });

  // filter
  el("wo-filter").addEventListener("input", () => {
    clearTimeout(window._wo_t);
    window._wo_t = setTimeout(refreshWorkouts, 250);
  });

  // delete workout
  el("wo-delete").addEventListener("click", async () => {
    if (!state.selectedId) return;
    if (!confirm("Delete this workout? Items will be removed.")) return;
    try {
      await apiDeleteWorkout(state.selectedId);
      state.selectedId = null;
      setEditorEnabled(false);
      await refreshWorkouts();

      // clear heatmap/chips
      _lastSummary = null;
      const fctx = getCtx("front"); if (fctx) fctx.clearRect(0,0,fctx.canvas.width,fctx.canvas.height);
      const bctx = getCtx("back");  if (bctx) bctx.clearRect(0,0,bctx.canvas.width,bctx.canvas.height);
      el("chips-primary").innerHTML = "";
      el("chips-secondary").innerHTML = "";
      document.querySelector("#items-table tbody").innerHTML = "";
      el("wo-title").textContent = "No workout selected";
    } catch (e) { alert(e.message || "Delete failed"); }
  });

  // add item
// add item
el("item-add").addEventListener("click", async () => {
  if (!state.selectedId) return;
  const exId = Number(el("item-ex-select").value);
  if (!exId) return alert("Choose an exercise");

  const cat = exCategoryById.get(exId) || '';

  // read inputs once
  const vSets   = el('item-sets').value;
  const vReps   = el('item-reps').value;
  const vWeight = el('item-weight').value; // for cardio, this is "Pace/HR (optional)"

  let payload;

  if (cat === 'cardio') {
    // minutes -> planned_sets (int), distance -> planned_reps (float), notes <- pace/hr text
    const minutes  = Number.isFinite(parseInt(vSets, 10)) ? parseInt(vSets, 10) : null;
    const distance = Number.isFinite(parseFloat(vReps))   ? parseFloat(vReps)   : null;
    const note     = (vWeight || '').trim() || null;

    payload = {
      exercise_id: exId,
      planned_sets: minutes,
      planned_reps: distance,
      planned_weight: null,  // keep numeric-only field empty for cardio
      notes: note
    };
  } else {
    // original strength behavior
    const sets   = Number.isFinite(parseInt(vSets, 10)) ? parseInt(vSets, 10) : null;
    const reps   = Number.isFinite(parseInt(vReps, 10)) ? parseInt(vReps, 10) : null;
    const weight = Number.isFinite(parseFloat(vWeight)) ? parseFloat(vWeight) : null;

    payload = {
      exercise_id: exId,
      planned_sets: sets,
      planned_reps: reps,
      planned_weight: weight,
      notes: null
    };
  }

  try {
    await apiAddItem(state.selectedId, payload);
    // clear fields
    el('item-sets').value = '';
    el('item-reps').value = '';
    el('item-weight').value = '';
    await refreshItems();
  } catch (e) { alert(e.message || "Add failed"); }
});

  await initExercisesSelect();
  await refreshWorkouts();
  setEditorEnabled(false);

  // ensure canvases draw once images have measured sizes
  const imgs = [...document.querySelectorAll(".bodyimg img")];
  await Promise.all(imgs.map(img => (img.complete ? Promise.resolve() : new Promise(r => img.onload = r))));
  if (state.selectedId) await refreshItems();
});

// select → console log
const sel = el("item-ex-select");
if (sel) {
  sel.addEventListener("change", () => {
    const id = Number(sel.value);
    const ex = state.exercises.find(e => e.id === id);
    console.log("[workouts] selected:", id, ex && ex.name);
  });
}

// ========== tiny utils ==========
function toInt(v)  { const n = parseInt(v, 10); return Number.isFinite(n) ? n : null; }
function toFloat(v){ const n = parseFloat(v);   return Number.isFinite(n) ? n : null; }