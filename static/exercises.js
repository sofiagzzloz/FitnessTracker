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
  const url = `/api/external/exercises?q=${encodeURIComponent(q)}&limit=10`;
  const res = await fetch(url);
  if (!res.ok) {
    const txt = await res.text().catch(() => '');
    throw new Error(`External search failed ${res.status}: ${txt || res.statusText}`);
  }
  return res.json();
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

  const tokens = (q || '').toLowerCase().split(/\s+/).filter(Boolean);

  // client-side relevance guard
  const filtered = tokens.length
    ? list.filter(it => {
        const name = (it.name || '').toLowerCase();
        return tokens.some(t => name.includes(t));
      })
    : list.slice();

  const show = filtered.length ? filtered : [];
  if (!show.length) {
    out.innerHTML = `<p class="hint">No matches for “<strong>${q}</strong>”.</p>`;
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
      </div>
    `;
    out.appendChild(card);

    card.querySelector(`#imp-${i}`).addEventListener('click', async () => {
      try {
        const saved = await importExternal(item);
        alert(`Imported: ${saved.name}`);
        await fetchLocalExercises(); // immediately refresh local table
      } catch (err) {
        console.error(err);
        alert(err.message || 'Import failed');
      }
    });
  });
}

// --- wire explore UI ---
function attachExploreHandlers() {
  const input = el('external-q');
  const btn   = el('external-btn');
  const out   = el('external-results');

  if (!input || !btn || !out) {
    console.warn('[Explore] elements not found; skipping wire-up.');
    return;
  }

  out.innerHTML = '<p class="hint">Type a name to search WGER.</p>';

  const run = async () => {
    const q = (input.value || '').trim();
    if (!q) { out.innerHTML = '<p class="hint">Type something to search.</p>'; return; }
    out.innerHTML = `<p class="hint">Searching “${q}”…</p>`;
    try {
      const list = await searchExternal(q);
      renderExternalResults(list, q);
    } catch (err) {
      console.error(err);
      out.innerHTML = `<p class="hint">Error: ${err.message || err}</p>`;
    }
  };

  btn.addEventListener('click', run);
  input.addEventListener('keydown', (e) => { if (e.key === 'Enter') run(); });

  // expose for manual testing in DevTools
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

async function browseExternal(reset=false) {
  if (_browseState.loading) return;
  _browseState.loading = true;
  const cont = el('browse-results');
  cont.innerHTML = cont.innerHTML || '<p class="hint">Loading…</p>';

  if (reset) _browseState.offset = 0;

  const params = new URLSearchParams();
  if (_browseState.muscle) params.set('muscle', _browseState.muscle);
  params.set('limit', String(_browseState.limit));
  params.set('offset', String(_browseState.offset));

  try {
    const res = await fetch(`/api/external/exercises/browse?${params.toString()}`);
    if (!res.ok) throw new Error(`Browse failed ${res.status}`);
    const data = await res.json();
    const items = data.items || [];
    if (reset) cont.innerHTML = '';

    renderBrowseResults(items, !!reset);
    _browseState.offset = data.next_offset ?? (_browseState.offset + _browseState.limit);
  } catch (err) {
    console.error(err);
    cont.innerHTML = `<p class="hint">Error: ${err.message || err}</p>`;
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
    browseExternal(true); // reset paging
  });

  more.addEventListener('click', () => {
    browseExternal(false); // next page
  });

  // init on load
  _browseState.muscle = sel.value || '';
  browseExternal(true);
}

document.addEventListener('DOMContentLoaded', () => {
  attachExploreHandlers();
  wireLocalFilters();
  fetchLocalExercises();
  fetchMuscles();
  attachBrowseHandlers();
});