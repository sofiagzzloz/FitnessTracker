function el(id) {
  return document.getElementById(id);
}

// --- small helpers ---
function debounce(fn, ms = 200) {
  let t;
  return (...args) => {
    clearTimeout(t);
    t = setTimeout(() => fn(...args), ms);
  };
}

let _browseState = { muscle: '', limit: 12, offset: 0, loading: false };

// normalize accents + lowercase
function norm(s) {
  return (s || "")
    .toString()
    .normalize("NFD")
    .replace(/\p{Diacritic}/gu, "")
    .toLowerCase();
}

// muscle guesser (used only if you keep the fallback in the search pane)
function guessMuscleFromQuery(q) {
  const t = norm(q);
  const map = {
    bicep: "biceps", biceps: "biceps",
    tricep: "triceps", triceps: "triceps",
    quad: "quads", quadriceps: "quads", quads: "quads",
    hamstring: "hams", hamstrings: "hams", hams: "hams",
    glute: "glutes", glutes: "glutes",
    calf: "calves", calves: "calves",
    chest: "chest", pec: "chest", pectoral: "chest", pectorals: "chest",
    back: "lats", lat: "lats", lats: "lats",
    delt: "delts", delts: "delts", shoulder: "delts", shoulders: "delts",
    abs: "abs", core: "abs",
  };
  for (const key of Object.keys(map)) if (t.includes(key)) return map[key];
  return null;
}

// simple caches and aborters
const _cache = { search: new Map(), browse: new Map() };
const _aborters = { search: null, browse: null };

function setLoading(el, msg="Loading…") {
  el.innerHTML = `<span class="spinner"></span><span>${msg}</span>`;
}


async function createExercise(payload) {
  const res = await fetch('/api/exercises', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const txt = await res.text().catch(() => '');
    throw new Error(txt || `Create failed (${res.status})`);
  }
  return res.json();
}

function attachAddExerciseHandler() {
  const btn = el('btn-add-exercise');
  const name = el('ex-name');
  const cat = el('ex-category');
  const unit = el('ex-unit');

  if (!btn || !name) return;

  btn.addEventListener('click', async () => {
    const n = (name.value || '').trim();
    const c = (cat?.value || 'strength').trim().toLowerCase();
    const u = (unit?.value || '').trim() || null;

    if (n.length < 2) {
      alert('Please enter a valid exercise name.');
      name.focus();
      return;
    }

    // backend expects Category enum: strength | cardio | mobility
    const validCats = new Set(['strength', 'cardio', 'mobility']);
    const category = validCats.has(c) ? c : 'strength';

    try {
      await createExercise({
        name: n,
        category,
        default_unit: u,
        equipment: null
      });
      // clear inputs and refresh table
      name.value = '';
      if (cat) cat.value = category;
      if (unit) unit.value = '';
      await fetchLocalExercises();
    } catch (err) {
      console.error(err);
      alert(err.message || 'Could not add exercise.');
    }
  });
}


// --- usage modal ---
function showUsageModal(usage) {
  const modal = el('delete-usage-modal');
  if (!modal) return alert('This exercise is used and cannot be deleted.');

  const blurb = el('usage-text');
  const links = el('usage-links');

  blurb.textContent =
    `${usage.exercise.name} is used in ${usage.counts.workouts} workout(s) and ${usage.counts.sessions} session(s). Remove it there first.`;
  links.innerHTML = '';

  if (usage.workouts && usage.workouts.length > 0) {
    const a = document.createElement('a');
    a.href = `/workouts?exercise_id=${usage.exercise.id}`;
    a.textContent = 'View related workouts';
    links.appendChild(a);
  }
  if (usage.sessions && usage.sessions.length > 0) {
    const a = document.createElement('a');
    a.href = `/sessions?exercise_id=${usage.exercise.id}`;
    a.textContent = 'View related sessions';
    links.appendChild(a);
  }

  modal.classList.remove('hidden');
}

document.addEventListener('click', (ev) => {
  if (ev.target && el('usage-close') && ev.target.id === 'usage-close') {
    el('delete-usage-modal').classList.add('hidden');
  }
});

// --- backend calls ---
async function searchExternal(q) {
  const key = norm(q);
  if (_cache.search.has(key)) return _cache.search.get(key);

  // cancel previous search
  if (_aborters.search) _aborters.search.abort();
  _aborters.search = new AbortController();

  const url = `/api/external/exercises?q=${encodeURIComponent(q)}&limit=20`;
  const res = await fetch(url, { signal: _aborters.search.signal });
  if (!res.ok) {
    const txt = await res.text().catch(() => '');
    throw new Error(`External search failed ${res.status}: ${txt || res.statusText}`);
  }
  const data = await res.json();
  _cache.search.set(key, data);
  return data;
}

// --- delete one exercise ---
async function deleteExercise(id) {
  const res = await fetch(`/api/exercises/${id}`, { method: 'DELETE' });

  if (res.status === 204) {
    return { status: "deleted" };
  }

  if (res.status === 409) {
    // Try to load usage; if it fails, still show a generic modal
    try {
      const usageRes = await fetch(`/api/exercises/${id}/usage`);
      if (usageRes.ok) {
        const usage = await usageRes.json();
        return { status: "in_use", usage };
      }
      // usage endpoint returned non-OK
      return {
        status: "in_use",
        usage: {
          exercise: { id, name: "This exercise" },
          workouts: [],
          sessions: [],
          counts: { workouts: 0, sessions: 0 }
        }
      };
    } catch (err) {
      console.error("usage fetch failed", err);
      return {
        status: "in_use",
        usage: {
          exercise: { id, name: "This exercise" },
          workouts: [],
          sessions: [],
          counts: { workouts: 0, sessions: 0 }
        }
      };
    }
  }

  const txt = await res.text().catch(() => "");
  return { status: "error", message: txt || `Delete failed (${res.status})` };
}

// --- import external exercise ---
async function importExternal(obj) {
  const res = await fetch('/api/external/exercises/import', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(obj),
  });
  if (!res.ok) {
    const txt = await res.text().catch(() => '');
    throw new Error(`Import failed ${res.status}: ${txt || res.statusText}`);
  }
  return res.json();
}

// --- external explore rendering ---
function renderExternalResults(list, q) {
  const out = el('external-results');
  if (!out) return;
  out.innerHTML = '';

  const tokens = norm(q).split(/\s+/).filter(Boolean);
  const filtered = tokens.length
    ? list.filter(it => {
        const name = norm(it.name || "");
        return tokens.some(t => name.includes(t));
      })
    : list.slice();

  const show = filtered.length ? filtered : [];
  if (!show.length) {
    out.innerHTML = `<p class="hint">No results for “<strong>${q}</strong>”.</p>`;
    return;
  }

  show.forEach((item, i) => {
    const card = document.createElement('div');
    card.className = 'card';
    card.style.marginTop = '8px';

    const prim = (item.muscles?.primary || []).join(', ');
    const sec  = (item.muscles?.secondary || []).join(', ');
    const muscles = prim || sec ? ` • muscles: ${prim}${sec ? ` (sec: ${sec})` : ''}` : '';

    card.innerHTML = `
      <div style="display:flex;justify-content:space-between;align-items:center;gap:12px">
        <div>
          <div style="font-weight:700">${item.name}</div>
          <div class="hint">${item.category || ''}${muscles}</div>
        </div>
        <button type="button" class="primary" id="imp-${i}">Import</button>
      </div>`;
    out.appendChild(card);

    card.querySelector(`#imp-${i}`).addEventListener('click', async () => {
      try {
        const saved = await importExternal(item);
        alert(`Imported: ${saved.name}`);
        await fetchLocalExercises();
      } catch (err) {
        console.error(err);
        alert(err.message || 'Import failed');
      }
    });
  });
}

function attachTabs() {
  const tabSearch = el('tab-search');
  const tabBrowse = el('tab-browse');
  const paneSearch = el('pane-search');
  const paneBrowse = el('pane-browse');

  if (!tabSearch || !tabBrowse || !paneSearch || !paneBrowse) return;

  const activate = (which) => {
    // buttons
    tabSearch.classList.toggle('active', which === 'search');
    tabBrowse.classList.toggle('active', which === 'browse');
    // panes
    paneSearch.classList.toggle('active', which === 'search');
    paneBrowse.classList.toggle('active', which === 'browse');
  };

  tabSearch.addEventListener('click', () => activate('search'));
  tabBrowse.addEventListener('click', () => activate('browse'));

  // default to search on load
  activate('search');
}

function attachExploreHandlers() {
  const input = el('external-q');
  const btn   = el('external-btn');
  const out   = el('external-results');

  if (!input || !btn || !out) return;

  out.innerHTML = '<p class="hint">Type at least 2 letters…</p>';

  const run = async () => {
    const q = (input.value || '').trim();
    if (q.length < 2) { out.innerHTML = '<p class="hint">Type at least 2 letters…</p>'; return; }

    setLoading(out, `Searching “${q}”…`);
    try {
      const list = await searchExternal(q);
      renderExternalResults(list, q);

      // Optional soft-fallback to browse by muscle if 0
      if (!out.querySelector('.card')) {
        const muscle = guessMuscleFromQuery(q);
        if (muscle) {
          setLoading(out, `No direct matches. Showing ${muscle}…`);
          const browse = await browseExternalFetch({ muscle, limit: 20, offset: 0 });
          renderExternalResults(browse, q);
          if (!out.querySelector('.card')) {
            out.innerHTML = `<p class="hint">No results for “${q}”.</p>`;
          }
        } else {
          out.innerHTML = `<p class="hint">No results for “${q}”.</p>`;
        }
      }
    } catch (err) {
      if (err.name === 'AbortError') return; // new search started; ignore
      console.error(err);
      out.innerHTML = `<p class="hint">Error: ${err.message || err}</p>`;
    }
  };

  btn.addEventListener('click', run);
  input.addEventListener('keydown', (e) => { if (e.key === 'Enter') run(); });
  input.addEventListener('input', debounce(() => {
    // optional: run on stop-typing
    // run();
  }, 500));

  // expose for DevTools
  window._extSearch = run;
}


// --- local exercises table ---
async function fetchLocalExercises() {
  const q = (el('ex-q')?.value || '').trim();
  const cat = (el('ex-cat-filter')?.value || '').trim();

  const params = new URLSearchParams();
  if (q) params.set('q', q);
  if (cat) params.set('category', cat);
  params.set('limit', '100');

  const res = await fetch(`/api/exercises?${params.toString()}`);
  if (!res.ok) return;
  const rows = await res.json();
  renderLocalExercises(rows);
}

function renderLocalExercises(rows) {
  const tbody = document.querySelector('#ex-table tbody');
  if (!tbody) return;
  tbody.innerHTML = rows.map(r => `
    <tr data-id="${r.id}">
      <td>${r.id}</td>
      <td>${r.name}</td>
      <td>${r.category ? `<span class="badge">${r.category}</span>` : ''}</td>
      <td>${r.default_unit || ''}</td>
      <td class="right">
        <button type="button" class="warn ex-del" data-id="${r.id}">Delete</button>
      </td>
    </tr>
  `).join('');
}

function wireLocalFilters() {
  const q = el('ex-q');
  const cat = el('ex-cat-filter');
  if (q) q.addEventListener('input', debounce(fetchLocalExercises, 250));
  if (cat) cat.addEventListener('input', debounce(fetchLocalExercises, 250));
}

// --- boot ---
document.addEventListener('DOMContentLoaded', () => {
  attachExploreHandlers();
  wireLocalFilters();
  fetchLocalExercises(); // initial load of your local library
});

document.addEventListener('click', async (e) => {
  const btn = e.target.closest('.ex-del');
  if (!btn) return;

  const id = btn.getAttribute('data-id');
  if (!id) return;

  const ok = confirm('Delete this exercise? This will fail if it is used in a workout or session.');
  if (!ok) return;

  const result = await deleteExercise(id);

  if (result.status === "deleted") {
    // remove row and/or refresh
    const tr = document.querySelector(`#ex-table tbody tr[data-id="${id}"]`);
    if (tr) tr.remove();
    return;
  }

  if (result.status === "in_use") {
    showUsageModal(result.usage); // <- opens the modal you added to HTML
    return;
  }

  // error fallback
  alert(result.message || "Delete failed");
});

async function fetchMuscles() {
  try {
    const res = await fetch('/api/external/muscles');
    const list = await res.json();
    const sel = el('browse-muscle');
    if (sel && Array.isArray(list)) {
      list.forEach(m => {
        const opt = document.createElement('option');
        opt.value = m.slug;
        opt.textContent = m.label;
        sel.appendChild(opt);
      });
    }
  } catch (_) { /* ignore */ }
}

async function browseExternalFetch({ muscle, limit, offset }) {
  const key = `${muscle || 'all'}|${limit}|${offset}`;
  if (_cache.browse.has(key)) return _cache.browse.get(key);

  if (_aborters.browse) _aborters.browse.abort();
  _aborters.browse = new AbortController();

  const params = new URLSearchParams();
  if (muscle) params.set('muscle', muscle);
  params.set('limit', String(limit));
  params.set('offset', String(offset));

  const res = await fetch(`/api/external/exercises/browse?${params.toString()}`, { signal: _aborters.browse.signal });
  if (!res.ok) throw new Error(`Browse failed ${res.status}`);
  const data = await res.json();
  const items = data?.items || [];
  _cache.browse.set(key, items);
  return items;
}

async function browseExternal(reset=false) {
  if (_browseState.loading) return;
  _browseState.loading = true;

  const cont = el('browse-results');
  if (reset) cont.innerHTML = '';
  setLoading(cont, 'Loading…');

  if (reset) _browseState.offset = 0;

  try {
    const items = await browseExternalFetch({
      muscle: _browseState.muscle || null,
      limit: _browseState.limit,
      offset: _browseState.offset
    });

    if (reset) cont.innerHTML = '';
    renderBrowseResults(items, !!reset);
    _browseState.offset += _browseState.limit;

    // enable/disable Load more
    el('browse-more').disabled = items.length < _browseState.limit;
  } catch (err) {
    if (err.name !== 'AbortError') {
      console.error(err);
      cont.innerHTML = `<p class="hint">Error: ${err.message || err}</p>`;
    }
  } finally {
    _browseState.loading = false;
  }
}

function renderBrowseResults(items, firstPage) {
  const cont = el('browse-results');
  if (!cont) return;
  if (firstPage && !items.length) {
    cont.innerHTML = '<p class="hint">No items found.</p>';
    return;
  }
  items.forEach((item, i) => {
    const card = document.createElement('div');
    card.className = 'card';
    card.style.marginTop = '8px';

    const prim = (item.muscles?.primary || []).join(', ');
    const sec  = (item.muscles?.secondary || []).join(', ');
    const muscles = prim || sec ? ` • muscles: ${prim}${sec ? ` (sec: ${sec})` : ''}` : '';

    const uid = `bimp-${Date.now()}-${Math.random().toString(36).slice(2)}`;
    card.innerHTML = `
      <div style="display:flex;justify-content:space-between;align-items:center;gap:12px">
        <div>
          <div style="font-weight:700">${item.name}</div>
          <div class="hint">${item.category || ''}${muscles}</div>
        </div>
        <button type="button" class="primary" id="${uid}">Import</button>
      </div>`;
    cont.appendChild(card);

    card.querySelector('#' + uid).addEventListener('click', async () => {
      try {
        const saved = await importExternal(item);
        alert(`Imported: ${saved.name}`);
        await fetchLocalExercises();
      } catch (err) {
        console.error(err);
        alert(err.message || 'Import failed');
      }
    });
  });
}

// wire browse UI
function attachBrowseHandlers() {
  const sel = el('browse-muscle');
  const btn = el('browse-btn');
  const more = el('browse-more');
  if (!sel || !btn || !more) return;

  sel.addEventListener('change', () => {
    _browseState.muscle = sel.value || '';
  });

  btn.addEventListener('click', () => {
    if (!_browseState.muscle) {
      el('browse-results').innerHTML = '<p class="hint">Pick a muscle first.</p>';
      more.disabled = true;
      return;
    }
    browseExternal(true);
  });

  more.addEventListener('click', () => {
    browseExternal(false);
  });
}

document.addEventListener('DOMContentLoaded', () => {
  attachTabs();                // <— NEW
  attachExploreHandlers();
  wireLocalFilters();
  fetchLocalExercises();
  fetchMuscles();
  attachBrowseHandlers();
  attachAddExerciseHandler();  // <— NEW
});