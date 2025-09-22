function el(id){ return document.getElementById(id); }

// --- small helpers ---
function debounce(fn, ms=200){
  let t; return (...args)=>{ clearTimeout(t); t = setTimeout(()=>fn(...args), ms); };
}

// --- backend calls ---
async function searchExternal(q) {
  const url = `/api/external/exercises?q=${encodeURIComponent(q)}&limit=10`;
  const res = await fetch(url);
  if (!res.ok) {
    const txt = await res.text().catch(()=> '');
    throw new Error(`External search failed ${res.status}: ${txt || res.statusText}`);
  }
  return res.json();
}

// --- delete one exercise ---
async function deleteExercise(id) {
  const res = await fetch(`/api/exercises/${id}`, { method: 'DELETE' });
  if (res.status === 204) return true;
  const txt = await res.text().catch(()=>'');
  throw new Error(txt || `Delete failed (${res.status})`);
}


async function importExternal(obj) {
  const res = await fetch('/api/external/exercises/import', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(obj),
  });
  if (!res.ok) {
    const txt = await res.text().catch(()=> '');
    throw new Error(`Import failed ${res.status}: ${txt || res.statusText}`);
  }
  return res.json();
}

// --- external explore rendering ---
function renderExternalResults(list, q) {
  const out = el('external-results');
  if (!out) return;

  out.innerHTML = '';

  // client-side relevance guard
  const filtered = list.filter(it => {
    const name = (it.name || '').toLowerCase();
    return tokens.length ? tokens.some(t => name.includes(t)) : true;
  });

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

  try {
    await deleteExercise(id);
    // remove row or refresh the whole list
    const tr = document.querySelector(`#ex-table tbody tr[data-id="${id}"]`);
    tr && tr.remove();
  } catch (err) {
    console.error(err);
    alert(err.message || 'Could not delete (it may be used by a workout/session).');
  }
});