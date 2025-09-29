function el(id) { return document.getElementById(id); }
function h(tag, attrs={}, ...kids){
  const n = document.createElement(tag);
  Object.entries(attrs||{}).forEach(([k,v]) => {
    if (k === 'class') n.className = v; else if (k === 'text') n.textContent = v; else n.setAttribute(k,v);
  });
  kids.forEach(k => n.appendChild(typeof k === 'string' ? document.createTextNode(k) : k));
  return n;
}

// ---- state ----
const state = {
  workouts: [],
  selectedId: null,
  items: [],
  exercises: [],
};

// ---- API helpers ----
async function apiListWorkouts(q){
  const res = await fetch('/api/workouts' + (q ? `?q=${encodeURIComponent(q)}` : ''));
  return res.ok ? res.json() : [];
}
async function apiCreateWorkout(name){
  const res = await fetch('/api/workouts', {
    method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({ name })
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}
async function apiDeleteWorkout(id){
  const res = await fetch(`/api/workouts/${id}`, { method:'DELETE' });
  if (!res.ok) throw new Error(await res.text());
}
async function apiListItems(tid){
  const res = await fetch(`/api/workouts/${tid}/items`);
  return res.ok ? res.json() : [];
}
async function apiAddItem(tid, payload){
  const res = await fetch(`/api/workouts/${tid}/items`, { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload) });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}
async function apiDeleteItem(itemId){
  const res = await fetch(`/api/workouts/items/${itemId}`, { method:'DELETE' });
  if (!res.ok) throw new Error(await res.text());
}

async function apiListExercises(){
  const cap = 200;
  // simple single page within server cap
  let res = await fetch(`/api/exercises?limit=${cap}`);
  if (res.ok) return res.json();

  // if somehow 422 again, retry with a smaller number
  if (res.status === 422) {
    res = await fetch('/api/exercises?limit=100');
    return res.ok ? res.json() : [];
  }

  const txt = await res.text().catch(()=> '');
  console.error('[workouts] /api/exercises failed:', res.status, txt);
  return [];
}

// ---- UI renderers ----
function renderWorkoutList(){
  const box = el('wo-list');
  box.innerHTML = '';
  if (!state.workouts.length) {
    box.innerHTML = '<p class="muted">No workouts yet.</p>';
    return;
  }
  state.workouts.forEach(w => {
    const a = h('button', { class: 'tab', style:'width:100%; text-align:left' });
    a.textContent = w.name;
    a.addEventListener('click', () => selectWorkout(w.id));
    if (w.id === state.selectedId) a.classList.add('active');
    box.appendChild(a);
  });
}

function setEditorEnabled(enabled){
  el('wo-empty').style.display = enabled ? 'none' : '';
  el('wo-editor').style.display = enabled ? '' : 'none';
  el('wo-delete').disabled = !enabled;
}

function renderItems(){
  const tb = document.querySelector('#items-table tbody');
  tb.innerHTML = '';
  if (!state.items.length) {
    tb.innerHTML = '<tr><td colspan="4" class="muted">No items yet.</td></tr>';
    return;
  }
  state.items.forEach((it, idx) => {
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td>${idx+1}</td>
      <td>${it.exercise_id}</td>
      <td>${planText(it)}</td>
      <td class="right"><button class="btn-small danger" data-id="${it.id}">Remove</button></td>
    `;
    tb.appendChild(tr);
  });

  // resolve exercise names
  const map = new Map(state.exercises.map(e => [e.id, e]));
  [...tb.querySelectorAll('tr')].forEach((tr, i) => {
    const it = state.items[i];
    const ex = map.get(it.exercise_id);
    if (ex) tr.children[1].textContent = ex.name;
  });

  // wire deletes
  tb.querySelectorAll('button[data-id]').forEach(btn => {
    btn.addEventListener('click', async () => {
      const id = Number(btn.getAttribute('data-id'));
      if (!confirm('Remove item?')) return;
      try {
        await apiDeleteItem(id);
        await refreshItems();
      } catch (e) { alert(e.message || 'Delete failed'); }
    });
  });
}

function planText(it){
  const parts = [];
  if (it.planned_sets) parts.push(`${it.planned_sets}x`);
  if (it.planned_reps) parts.push(`${it.planned_reps}`);
  if (it.planned_weight) parts.push(`${it.planned_weight}`);
  if (!parts.length) return '—';
  return parts.join(' ');
}

// ---- MUSCLE MAP ----
const FRONT_POS = {
  chest:        [{x:50, y:21}],
  front_delts:  [{x:30, y:16},{x:70, y:16}],
  side_delts:   [{x:24, y:20},{x:76, y:20}],
  biceps:       [{x:23, y:38, s:.95},{x:77, y:38, s:.95}],
  triceps:      [{x:23, y:48, s:.95},{x:77, y:48, s:.95}],
  abs:          [{x:50, y:35, s:.95}],
  quads:        [{x:44, y:70, s:1.1},{x:56, y:70, s:1.1}],
  calves:       [{x:44, y:86, s:.95},{x:56, y:86, s:.95}],
};
const BACK_POS = {
  traps:        [{x:50, y:16}],
  lats:         [{x:40, y:28, s:1.1},{x:60, y:28, s:1.1}],
  lower_back:   [{x:50, y:45}],
  glutes:       [{x:50, y:61, s:1.15}],
  hams:         [{x:44, y:73, s:1.1},{x:56, y:73, s:1.1}],
  calves:       [{x:44, y:87, s:.95},{x:56, y:87, s:.95}],
};

let _lastSummary = { primary:{}, secondary:{} };

function getCanvasCtx(imgId, canvasId){
  const img = el(imgId);
  const canvas = el(canvasId);
  if (!img || !canvas) return null;

  // ensure the canvas matches the displayed image size (with DPR)
  const rect = img.getBoundingClientRect();
  const dpr = window.devicePixelRatio || 1;

  canvas.style.width  = rect.width + 'px';
  canvas.style.height = rect.height + 'px';
  canvas.width  = Math.max(1, Math.round(rect.width  * dpr));
  canvas.height = Math.max(1, Math.round(rect.height * dpr));

  const ctx = canvas.getContext('2d');
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);  // draw using CSS pixels
  ctx.clearRect(0, 0, rect.width, rect.height);

  return { ctx, w: rect.width, h: rect.height };
}

function clearHeat(){
  const f = getCanvasCtx('body-front', 'front-canvas');
  const b = getCanvasCtx('body-back',  'back-canvas');
  // getCanvasCtx() already clears, so nothing else to do.
}

function levelFromCount(c, max){
  if (!max) return 1;
  const r = c / max;
  if (r >= 0.9) return 4;
  if (r >= 0.6) return 3;
  if (r >= 0.3) return 2;
  return 1;
}

function drawBlob(ctx, w, h, xPct, yPct, role, level, scale=1){
  const x = (xPct / 100) * w;
  const y = (yPct / 100) * h;

  // base radius in CSS px, scaled by intensity and optional muscle tweak
  const base = 22; // adjust to taste
  const r = base * (0.75 + 0.25 * level) * (scale || 1);

  const color = role === 'primary' ? '44,193,255' : '119,215,255';

  const grad = ctx.createRadialGradient(x, y, 0, x, y, r);
  grad.addColorStop(0.0, `rgba(${color}, 0.65)`);
  grad.addColorStop(0.5, `rgba(${color}, 0.25)`);
  grad.addColorStop(1.0, `rgba(${color}, 0.0)`);

  ctx.beginPath();
  ctx.arc(x, y, r, 0, Math.PI * 2);
  ctx.fillStyle = grad;
  ctx.fill();
}

function pretty(slug){ return slug.replace(/_/g,' '); }

function applyMapColors(summary){
  _lastSummary = summary || { primary:{}, secondary:{} };

  const f = getCanvasCtx('body-front', 'front-canvas');
  const b = getCanvasCtx('body-back',  'back-canvas');
  if (!f || !b) return;

  const prim = _lastSummary.primary || {};
  const sec  = _lastSummary.secondary || {};

  // chips
  const cp = el('chips-primary'); cp.innerHTML = '';
  const cs = el('chips-secondary'); cs.innerHTML = '';
  const note = el('map-note');

  const pKeys = Object.keys(prim);
  const sKeys = Object.keys(sec);
  const maxP = Math.max(0, ...Object.values(prim));
  const maxS = Math.max(0, ...Object.values(sec));

  // primary
  pKeys.forEach(slug => {
    const lvl = levelFromCount(prim[slug], maxP);
    (FRONT_POS[slug] || []).forEach(h => drawBlob(f.ctx, f.w, f.h, h.x, h.y, 'primary', lvl, h.s));
    (BACK_POS[slug]  || []).forEach(h => drawBlob(b.ctx, b.w, b.h, h.x, h.y, 'primary', lvl, h.s));
    cp.appendChild(hEl('span', {class:'chip'}, `${pretty(slug)} ×${prim[slug]}`));
  });

  // secondary (skip ones already primary)
  sKeys.forEach(slug => {
    if (prim[slug]) return;
    const lvl = levelFromCount(sec[slug], maxS);
    (FRONT_POS[slug] || []).forEach(h => drawBlob(f.ctx, f.w, f.h, h.x, h.y, 'secondary', lvl, h.s));
    (BACK_POS[slug]  || []).forEach(h => drawBlob(b.ctx, b.w, b.h, h.x, h.y, 'secondary', lvl, h.s));
    cs.appendChild(hEl('span', {class:'chip'}, `${pretty(slug)} ×${sec[slug]}`));
  });

  note.textContent = (pKeys.length || sKeys.length) ? '' : 'Add items to see muscles.';
}

// tiny helper because we shadowed `h` above
function hEl(tag, attrs={}, ...kids){ return h(tag, attrs, ...kids); }

// Re-render heat when the window resizes (so canvases stay aligned)
window.addEventListener('resize', () => applyMapColors(_lastSummary));

// ---- actions ----
async function selectWorkout(id){
  state.selectedId = id;
  const w = state.workouts.find(x => x.id === id);
  el('wo-title').textContent = w ? w.name : 'Workout';
  setEditorEnabled(true);
  renderWorkoutList();
  const imgs = [...document.querySelectorAll('.bodyimg img')];
  await Promise.all(imgs.map(img => img.complete ? Promise.resolve() : new Promise(r => img.onload = r)));
  await refreshItems();
}
async function apiTemplateMuscles(tid){
  const res = await fetch(`/api/workouts/${tid}/muscles`);
  if (!res.ok) return { primary:{}, secondary:{} };
  return res.json();
}

async function refreshItems(){
  if (!state.selectedId) return;
  state.items = await apiListItems(state.selectedId);
  renderItems();

  try {
    const summary = await apiTemplateMuscles(state.selectedId);
    applyMapColors(summary);
  } catch (e) {
    console.error('[workouts] muscle map load failed:', e);
    applyMapColors({ primary:{}, secondary:{} }); // keep UI stable
  }
}

async function refreshWorkouts(){
  state.workouts = await apiListWorkouts(el('wo-filter').value.trim());
  renderWorkoutList();
}

async function initExercisesSelect(){
  try {
    console.log('[workouts] loading exercises…');
    state.exercises = await apiListExercises();
    console.log('[workouts] exercises count =', state.exercises.length);
    console.log('[workouts] loaded exercises:', state.exercises.length, state.exercises.slice(0, 5));

    const sel = el('item-ex-select');
    if (!sel) { console.warn('[workouts] missing #item-ex-select'); return; }

    sel.innerHTML = '<option value="">Choose…</option>';
    if (!state.exercises.length) {
      // show a friendly hint
      const opt = document.createElement('option');
      opt.value = '';
      opt.textContent = 'No local exercises yet — import or add some on the Exercises page';
      sel.appendChild(opt);
      return;
    }

    state.exercises.forEach(ex => {
      const opt = document.createElement('option');
      opt.value = ex.id;
      opt.textContent = ex.name;  // <- show names, not IDs
      sel.appendChild(opt);
    });
  } catch (e) {
    console.error('[workouts] failed to load exercises', e);
    alert(e.message || 'Could not load exercises list.');
  }
}

// ---- wiring ----
document.addEventListener('DOMContentLoaded', async () => {
  // create
  el('wo-create').addEventListener('click', async () => {
    const name = (el('wo-new-name').value || '').trim();
    if (!name) return alert('Name required');
    try {
      const w = await apiCreateWorkout(name);
      el('wo-new-name').value = '';
      await refreshWorkouts();
      await selectWorkout(w.id);
    } catch (e) { alert(e.message || 'Create failed'); }
  });

  // filter
  el('wo-filter').addEventListener('input', () => {
    clearTimeout(window._wo_t);
    window._wo_t = setTimeout(refreshWorkouts, 250);
  });

  // delete workout
  el('wo-delete').addEventListener('click', async () => {
    if (!state.selectedId) return;
    if (!confirm('Delete this workout? Items will be removed.')) return;
    try {
      await apiDeleteWorkout(state.selectedId);
      state.selectedId = null;
      setEditorEnabled(false);
      await refreshWorkouts();
      resetMapColors();
      clearHotspots();
      el('chips-primary').innerHTML = '';
      el('chips-secondary').innerHTML = '';
      el('items-table').querySelector('tbody').innerHTML = '';
      el('wo-title').textContent = 'No workout selected';
    } catch (e) { alert(e.message || 'Delete failed'); }
  });

  // add item
  el('item-add').addEventListener('click', async () => {
    if (!state.selectedId) return;
    const exId = Number(el('item-ex-select').value);
    if (!exId) return alert('Choose an exercise');
    const payload = {
      exercise_id: exId,
      planned_sets: toInt(el('item-sets').value),
      planned_reps: toInt(el('item-reps').value),
      planned_weight: toFloat(el('item-weight').value),
    };
    try {
      await apiAddItem(state.selectedId, payload);
      // clear
      el('item-sets').value = '';
      el('item-reps').value = '';
      el('item-weight').value = '';
      await refreshItems();
    } catch (e) { alert(e.message || 'Add failed'); }
  });

  await initExercisesSelect();
  await refreshWorkouts();
  setEditorEnabled(false);
  resetMapColors();
  clearHotspots();
});

function resizeHeatmaps(){
  ensureCanvasHosts();
  const frontImg = document.querySelector('.bodyimg.front img') || el('body-front');
  const backImg  = document.querySelector('.bodyimg.back img')  || el('body-back');
  const frontCv  = document.querySelector('.bodyimg.front canvas') || el('front-canvas');
  const backCv   = document.querySelector('.bodyimg.back canvas')  || el('back-canvas');
  ensureCanvasSize(frontImg, frontCv);
  ensureCanvasSize(backImg,  backCv);
  if (state.selectedId) {
    apiTemplateMuscles(state.selectedId).then(applyMapColors).catch(()=>{});
  }
}
['load','resize'].forEach(evt => window.addEventListener(evt, resizeHeatmaps));

const sel = el('item-ex-select');
sel.addEventListener('change', () => {
  const id = Number(sel.value);
  const ex = state.exercises.find(e => e.id === id);
  console.log('[workouts] selected:', id, ex && ex.name);
});

// utils
function toInt(v){ const n = parseInt(v,10); return Number.isFinite(n) ? n : null; }
function toFloat(v){ const n = parseFloat(v); return Number.isFinite(n) ? n : null; }
