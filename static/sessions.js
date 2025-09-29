// ---------- cookie-aware fetch ----------
async function apiFetch(url, opts = {}) {
  const merged = {
    credentials: "include",
    headers: { "Content-Type": "application/json", ...(opts.headers || {}) },
    ...opts,
  };
  const res = await fetch(url, merged);
  if (res.status === 401 && !url.startsWith("/api/auth")) {
    location.href = "/login";
    throw new Error("Unauthorized");
  }
  return res;
}

// -------- tiny dom helpers --------
function el(id){ return document.getElementById(id); }
function h(tag, attrs={}, ...kids){
  const n = document.createElement(tag);
  for (const [k,v] of Object.entries(attrs||{})) {
    if (k === 'class') n.className = v;
    else if (k === 'text') n.textContent = v;
    else n.setAttribute(k, v);
  }
  for (const k of kids) n.appendChild(typeof k === 'string' ? document.createTextNode(k) : k);
  return n;
}

// -------- state --------
const state = {
  workouts: [],
  sessions: [],
  selectedId: null,
  sessionMap: new Map(),
  items: [],
  exercises: [],
  plannedByExId: new Map(),
};

// -------- API --------
async function apiListWorkouts(q){
  const res = await apiFetch('/api/workouts' + (q ? `?q=${encodeURIComponent(q)}` : ''));
  return res.ok ? res.json() : [];
}

async function apiListExercises(){
  const res = await apiFetch('/api/exercises?limit=200');
  return res.ok ? res.json() : [];
}

async function apiListSessions(params={}){
  const qs = new URLSearchParams();
  if (params.on_date) qs.set('on_date', params.on_date);
  if (params.start_date) qs.set('start_date', params.start_date);
  if (params.end_date) qs.set('end_date', params.end_date);
  const res = await apiFetch('/api/sessions' + (qs.toString() ? `?${qs}` : ''));
  return res.ok ? res.json() : [];
}

async function apiCreateSession(payload){
  const res = await apiFetch('/api/sessions', { method:'POST', body: JSON.stringify(payload) });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

async function apiReadSession(id){
  const res = await apiFetch(`/api/sessions/${id}`);
  return res.ok ? res.json() : null;
}

async function apiListSessionItems(sessionId){
  const res = await apiFetch(`/api/sessions/${sessionId}/items`);
  return res.ok ? res.json() : [];
}

async function apiDeleteSessionItem(sessionId, itemId){
  const res = await apiFetch(`/api/sessions/${sessionId}/items/${itemId}`, { method:'DELETE' });
  if (!res.ok) throw new Error(await res.text());
}

async function apiAddSessionItem(sessionId, payload){
  const res = await apiFetch(`/api/sessions/${sessionId}/items`, { method:'POST', body: JSON.stringify(payload) });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

async function apiPatchSessionItem(sessionId, itemId, patch){
  const res = await apiFetch(`/api/sessions/${sessionId}/items/${itemId}`, { method:'PATCH', body: JSON.stringify(patch) });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

async function apiListWorkoutItems(workoutId){
  const res = await apiFetch(`/api/workouts/${workoutId}/items`);
  return res.ok ? res.json() : [];
}
async function apiWorkoutMuscles(workoutId){
  const res = await apiFetch(`/api/workouts/${workoutId}/muscles`);
  return res.ok ? res.json() : {primary:{},secondary:{}};
}

// -------- left column --------
function renderSessionList(){
  const box = el('sess-list');
  box.innerHTML = '';
  if (!state.sessions.length) {
    box.innerHTML = '<p class="muted">No sessions yet.</p>';
    return;
  }
  state.sessions.forEach(s => {
    const btn = h('button', { class:'tab', style:'width:100%; text-align:left' });
    const title = s.title ? ` — ${s.title}` : '';
    btn.textContent = `${s.date}${title}`;
    if (s.id === state.selectedId) btn.classList.add('active');
    btn.addEventListener('click', () => selectSession(s.id));
    box.appendChild(btn);
  });
}

function setEditorEnabled(enabled){
  el('sess-empty').style.display = enabled ? 'none' : '';
  el('sess-editor').style.display = enabled ? '' : 'none';
}

// -------- table + actions --------
function plannedText(exId){
  const p = state.plannedByExId.get(exId);
  if (!p) return '—';
  const bits = [];
  if (p.planned_sets) bits.push(`${p.planned_sets}x`);
  if (p.planned_reps) bits.push(`${p.planned_reps}`);
  if (p.planned_weight) bits.push(`${p.planned_weight}`);
  return bits.length ? bits.join(' ') : '—';
}

function renderItems(){
  const tb = el('sess-items-tb');
  tb.innerHTML = '';
  if (!state.items.length){
    tb.innerHTML = '<tr><td colspan="5" class="muted">No items.</td></tr>';
    return;
  }

  state.items.forEach((it, idx) => {
    const tr = document.createElement('tr');

    // inputs for "Actual" (for now, we store in notes until you expose SessionSet)
    const inActual = h('input', { class:'input', value: it.notes || '', placeholder:'optional (e.g. 3x12 @ 50kg)' });
    const saveBtn  = h('button', { class:'btn-small', text:'Save' });
    saveBtn.addEventListener('click', async () => {
      try {
        // requires PATCH route (see below); if you skip adding it, remove this listener
        await apiPatchSessionItem(state.selectedId, it.id, { notes: inActual.value || null });
        it.notes = inActual.value || null;
      } catch (e) {
        alert(e.message || 'Could not save');
      }
    });

    const delBtn = h('button', { class:'btn-small danger', text:'Remove' });
    delBtn.addEventListener('click', async () => {
      if (!confirm('Remove this exercise from the session?')) return;
      try {
        await apiDeleteSessionItem(state.selectedId, it.id);
        await refreshItems(); // reload
      } catch (e) { alert(e.message || 'Delete failed'); }
    });

    tr.appendChild(h('td', { }, String(idx+1)));
    tr.appendChild(h('td', { }, it.exercise_name || it.exercise_id));
    tr.appendChild(h('td', { }, plannedText(it.exercise_id)));
    const actTd = h('td'); actTd.appendChild(inActual); tr.appendChild(actTd);
    const actBtns = h('td', { class:'right' }); actBtns.appendChild(saveBtn); actBtns.appendChild(document.createTextNode(' ')); actBtns.appendChild(delBtn);
    tr.appendChild(actBtns);

    tb.appendChild(tr);
  });
}

// -------- heatmap: reuse the workouts canvas painter --------
// (this is the minimal glue to call the same functions already in /static/workouts.js)
function pretty(slug){ return slug.replace(/_/g,' '); }

function ensureHeatmapCanvases(){
  const front = el('front-canvas');
  const back  = el('back-canvas');
  const fi = el('body-front'), bi = el('body-back');
  if (front && fi) { front.width = fi.clientWidth; front.height = fi.clientHeight; }
  if (back && bi)  { back.width  = bi.clientWidth;  back.height  = bi.clientHeight; }
}

async function drawSessionHeatmap(workoutTemplateId){
  // 1) get the server summary (template-based)
  let server = { primary:{}, secondary:{} };
  try {
    if (workoutTemplateId) {
      const s = await apiWorkoutMuscles(workoutTemplateId);
      if (s && (s.primary || s.secondary)) server = s;
    }
  } catch (_) { /* ignore */ }

  // 2) build a fallback summary from what’s on screen right now
  //    (guesses primaries from exercise names)
  let fallback = { primary:{}, secondary:{} };
  try {
    if (window.heatmapFallback) {
      fallback = window.heatmapFallback(state.items, state.exercises);
    }
  } catch (_) { /* ignore */ }

  // 3) merge – keep primaries as primary; don’t duplicate as secondary
  const merged = (window.heatmapMerge ? window.heatmapMerge(server, fallback) : server);

  // 4) size canvases and draw
  ensureHeatmapCanvases();
  if (window.applyMapColors) window.applyMapColors(merged);
}

// -------- selection / refresh --------
async function selectSession(id){
  // if called with null/undefined, clear the editor
  if (!id) {
    state.selectedId = null;
    el('sess-title').textContent = 'No session selected';
    setEditorEnabled(false);
    el('sess-delete') && (el('sess-delete').style.display = 'none');
    el('sess-items-tb').innerHTML = '';
    return;
  }

  state.selectedId = id;

  // ---- load / cache the session ----
  let s = state.sessionMap.get(id);
  if (!s) {
    try {
      s = await apiReadSession(id);
      if (s) state.sessionMap.set(id, s);
    } catch (e) {
      console.error('[sessions] failed to read session', e);
      alert('Could not load this session.');
      return;
    }
  }
  if (!s) return;

  // header + delete button visibility
  const suffix = s.title ? ` — ${s.title}` : '';
  el('sess-title').textContent = `${s.date}${suffix}`;
  if (el('sess-delete')) el('sess-delete').style.display = '';

  // show editor area
  setEditorEnabled(true);

  // ---- planned (from template) ----
  state.plannedByExId.clear();
  if (s.workout_template_id) {
    try {
      const tplItems = await apiListWorkoutItems(s.workout_template_id);
      tplItems.forEach(it => {
        state.plannedByExId.set(it.exercise_id, {
          planned_sets: it.planned_sets,
          planned_reps: it.planned_reps,
          planned_weight: it.planned_weight
        });
      });
    } catch (e) {
      console.warn('[sessions] template items load failed:', e);
    }
  }

  // ---- items table ----
  try {
    state.items = await apiListSessionItems(id);
  } catch (e) {
    console.error('[sessions] items load failed', e);
    state.items = [];
  }
  renderItems();

  // ---- chips + note (same shape as workouts) ----
  el('chips-primary').innerHTML = '';
  el('chips-secondary').innerHTML = '';
  el('map-note').textContent = state.items.length ? '' : 'No items.';

  // ---- heatmap (make sure canvases match the images) ----
  try {
    // wait for body images if needed
    const imgs = [el('body-front'), el('body-back')].filter(Boolean);
    await Promise.all(
      imgs.map(img => (img && !img.complete) ? new Promise(r => img.onload = r) : Promise.resolve())
    );

    // size canvases to images (same way workouts does)
    const fi = el('body-front'), bi = el('body-back');
    const fc = el('front-canvas'), bc = el('back-canvas');
    if (fi && fc) { fc.width = fi.clientWidth; fc.height = fi.clientHeight; }
    if (bi && bc) { bc.width = bi.clientWidth; bc.height = bi.clientHeight; }

    await drawSessionHeatmap(s.workout_template_id || null);
  } catch (e) {
    console.warn('[sessions] heatmap draw failed:', e);
  }

  // refresh left list highlighting
  renderSessionList();
}

el('sess-delete')?.addEventListener('click', async () => {
  const id = state.selectedId;
  if (!id) return;

  if (!confirm('Delete this session? This will remove all its items.')) return;

  try {
    const res = await fetch(`/api/sessions/${id}`, { method: 'DELETE' });
    if (!res.ok) {
      const msg = await res.text().catch(()=> '');
      throw new Error(msg || `Delete failed (HTTP ${res.status})`);
    }

    // Refresh the list and verify it’s gone
    await refreshSessionsList();
    const stillThere = state.sessions.some(s => s.id === id);

    // Reset the right panel
    state.selectedId = null;
    el('sess-title').textContent = 'No session selected';
    el('sess-items-tb').innerHTML = '';
    el('sess-empty').style.display = '';
    el('sess-editor').style.display = 'none';
    if (el('sess-delete')) el('sess-delete').style.display = 'none';

    // If it somehow persisted, surface that immediately
    if (stillThere) {
      alert('The session is still listed after delete. This usually means the server blocked the delete (FK constraint). See backend notes.');
    }
  } catch (e) {
    alert(e.message || 'Delete failed');
  }
});

async function refreshItems(){
  if (!state.selectedId) return;
  state.items = await apiListSessionItems(state.selectedId);
  renderItems();
}

async function refreshSessionsList(){
  state.sessions = await apiListSessions({});
  state.sessionMap.clear();
  state.sessions.forEach(s => state.sessionMap.set(s.id, s));
  renderSessionList();

  // If the currently selected id no longer exists, clear the editor
  if (state.selectedId && !state.sessions.some(s => s.id === state.selectedId)) {
    state.selectedId = null;
    el('sess-title').textContent = 'No session selected';
    setEditorEnabled(false);
    if (el('sess-delete')) el('sess-delete').style.display = 'none';
  }
}

// -------- wiring --------
document.addEventListener('DOMContentLoaded', async () => {
  // template select
  state.workouts  = await apiListWorkouts();
  state.exercises = await apiListExercises().catch(()=>[]);

  const tplSel = el('sess-template');
  if (tplSel) {
    tplSel.innerHTML = '<option value="">(none)</option>';
    state.workouts.forEach(w => {
      const opt = document.createElement('option');
      opt.value = w.id; opt.textContent = w.name;
      tplSel.appendChild(opt);
    });
  }

  // ad-hoc add (“Add to session”) keeps your current UI, just pointing to the session
  const addSel = el('add-ex-select');
  if (addSel) {
    addSel.innerHTML = '<option value="">Loading...</option>';
    addSel.innerHTML = '<option value="">Choose…</option>';
    state.exercises.forEach(e => {
      const opt = document.createElement('option');
      opt.value = e.id; opt.textContent = e.name;
      addSel.appendChild(opt);
    });
  }
  el('add-item')?.addEventListener('click', async () => {
    if (!state.selectedId) return alert('Open a session first');
    const exId = Number(el('add-ex-select')?.value || 0);
    const note = (el('add-ex-notes')?.value || '').trim();
    if (!exId) return alert('Choose an exercise');
    try {
      await apiAddSessionItem(state.selectedId, { exercise_id: exId, notes: note || null });
      el('add-ex-notes').value = '';
      await refreshItems();
    } catch (e) { alert(e.message || 'Add failed'); }
  });

  // Start session
  el('sess-create')?.addEventListener('click', async () => {   // FIXED: matches HTML id
    const tplId = Number(el('sess-template')?.value || 0) || null;
    const date  = (el('sess-date')?.value || '').trim();
    const title = (el('sess-title-input')?.value || '').trim() || null;
    const notes = (el('sess-notes')?.value || '').trim() || null;
    if (!date) return alert('Pick a date');
    try {
      const s = await apiCreateSession({ date, title, notes, workout_template_id: tplId });
      await refreshSessionsList();
      await selectSession(s.id);
      el('sess-title-input').value = '';
      el('sess-notes').value = '';
    } catch (e) { alert(e.message || 'Create failed'); }
  });

  // initial load
  await refreshSessionsList();
  if (state.sessions.length) await selectSession(state.sessions[0].id);

  // keep canvases sized
  window.addEventListener('resize', () => ensureHeatmapCanvases(), { passive:true });
});
