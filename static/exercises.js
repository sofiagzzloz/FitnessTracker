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

function el(id) { return document.getElementById(id); }

// --- small helpers ---
function debounce(fn, ms = 200) {
  let t;
  return (...args) => {
    clearTimeout(t);
    t = setTimeout(() => fn(...args), ms);
  };
}

// Normalize (remove accents) + lowercase + strip punctuation + collapse spaces
function norm(s) {
  if (!s) return "";
  return s
    .normalize("NFKD").replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[^\w\s]+/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

// Naive singularization
function _singular(t) {
  if (t.length > 3 && /[^aeiou]es$/.test(t)) return t.slice(0, -2);
  if (t.length > 3 && t.endsWith("s")) return t.slice(0, -1);
  return t;
}

// Tokenize with normalization + singularization
function tokens(s) {
  return norm(s).split(" ").filter(Boolean).map(_singular);
}

// Strict token-AND check
function passAllTokens(name, q) {
  const n = norm(name);
  const qt = tokens(q);
  return qt.length === 0 || qt.every(t => n.includes(t));
}

function setLoading(elm, msg = "Loading…") {
  if (!elm) return;
  elm.innerHTML = `<span class="spinner"></span><span>${msg}</span>`;
}

// --- state ---
let _browseState = { muscle: "", limit: 12, offset: 0, loading: false };
const _cache = { search: new Map(), browse: new Map() };
const _aborters = { search: null, browse: null };

// -----------------------------------------------------
// Add local exercise
// -----------------------------------------------------
async function createExercise(payload) {
  const res = await apiFetch("/api/exercises", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const txt = await res.text().catch(() => "");
    throw new Error(txt || `Create failed (${res.status})`);
  }
  return res.json();
}

function attachAddExerciseHandler() {
  const btn = el("btn-add-exercise");
  const name = el("ex-name");
  const cat  = el("ex-category");
  const unit = el("ex-unit");
  if (!btn || !name) return;

  btn.addEventListener("click", async () => {
    const n = (name.value || "").trim();
    const c = (cat && cat.value ? cat.value : "strength").trim().toLowerCase();
    const u = (unit && unit.value ? unit.value.trim() : "") || null;

    if (n.length < 2) {
      alert("Please enter a valid exercise name.");
      name.focus();
      return;
    }
    const validCats = new Set(["strength", "cardio", "mobility"]);
    const category = validCats.has(c) ? c : "strength";

    try {
      await createExercise({ name: n, category, default_unit: u, equipment: null });
      name.value = "";
      if (cat) cat.value = category;
      if (unit) unit.value = "";
      await fetchLocalExercises();
    } catch (err) {
      console.error(err);
      alert(err.message || "Could not add exercise.");
    }
  });
}

// -----------------------------------------------------
// Delete usage modal
// -----------------------------------------------------
function showUsageModal(usage) {
  const modal = el("delete-usage-modal");
  if (!modal) {
    alert("This exercise is used and cannot be deleted.");
    return;
  }

  const usageText = el("usage-text");
  const links = el("usage-links");
  if (usageText) {
    usageText.textContent = `${usage.exercise.name} is used in ${usage.counts.workouts} workout(s) and ${usage.counts.sessions} session(s). Remove it there first.`;
  }
  if (links) {
    links.innerHTML = "";
    if (usage.workouts && usage.workouts.length) {
      const a = document.createElement("a");
      a.href = `/workouts?exercise_id=${usage.exercise.id}`;
      a.textContent = "View related workouts";
      links.appendChild(a);
    }
    if (usage.sessions && usage.sessions.length) {
      const a = document.createElement("a");
      a.href = `/sessions?exercise_id=${usage.exercise.id}`;
      a.textContent = "View related sessions";
      links.appendChild(a);
    }
  }
  modal.classList.remove("hidden");
}

document.addEventListener("click", (ev) => {
  const target = ev.target;
  if (target && target.id === "usage-close") {
    const modal = el("delete-usage-modal");
    if (modal) modal.classList.add("hidden");
  }
});

// -----------------------------------------------------
// External search (NAME ONLY)
// -----------------------------------------------------
async function searchExternal(q) {
  const key = tokens(q).join(" ");
  if (_cache.search.has(key)) return _cache.search.get(key);

  if (_aborters.search) _aborters.search.abort();
  _aborters.search = new AbortController();

  const res = await apiFetch(
    `/api/external/exercises?q=${encodeURIComponent(q)}&limit=20`,
    { signal: _aborters.search.signal }
  );
  if (!res.ok) {
    const txt = await res.text().catch(() => "");
    throw new Error(`External search failed ${res.status}: ${txt || res.statusText}`);
  }
  const data = await res.json();
  _cache.search.set(key, data);
  return data;
}

function renderExternalResults(list, q) {
  const out = el("external-results");
  if (!out) return;
  out.innerHTML = "";

  const filtered = Array.isArray(list)
    ? (tokens(q).length ? list.filter(it => passAllTokens(it.name || "", q)) : list)
    : [];

  if (!filtered.length) {
    out.innerHTML = `<p class="hint">No results for “<strong>${q}</strong>”. Try a different name.</p>`;
    return;
  }

  filtered.forEach((item, i) => {
    const card = document.createElement("div");
    card.className = "card";
    card.style.marginTop = "8px";

    const prim = (item.muscles && item.muscles.primary ? item.muscles.primary : []).join(", ");
    const sec  = (item.muscles && item.muscles.secondary ? item.muscles.secondary : []).join(", ");
    const muscles = (prim || sec) ? ` • muscles: ${prim}${sec ? ` (sec: ${sec})` : ""}` : "";

    card.innerHTML = `
      <div style="display:flex;justify-content:space-between;align-items:center;gap:12px">
        <div>
          <div style="font-weight:700">${item.name}</div>
          <div class="hint">${item.category || ""}${muscles}</div>
        </div>
        <button type="button" class="primary" id="imp-${i}">Import</button>
      </div>`;
    out.appendChild(card);

    const importBtn = card.querySelector(`#imp-${i}`);
    if (importBtn) {
      importBtn.addEventListener("click", async () => {
        try {
          const saved = await importExternal(item);
          alert(`Imported: ${saved.name}`);
          await fetchLocalExercises();
        } catch (err) {
          console.error(err);
          alert(err.message || "Import failed");
        }
      });
    }
  });
}

function attachExploreHandlers() {
  const input = el("external-q");
  const btn   = el("external-btn");
  const out   = el("external-results");
  if (!input || !btn || !out) return;

  out.innerHTML = '<p class="hint">Type at least 2 letters…</p>';

  const run = async () => {
    const q = (input.value || "").trim();
    if (q.length < 2) {
      out.innerHTML = '<p class="hint">Type at least 2 letters…</p>';
      return;
    }
    setLoading(out, `Searching “${q}”…`);
    try {
      const list = await searchExternal(q);
      console.log("[ex-search] results:", Array.isArray(list) ? list.length : 0);
      renderExternalResults(list, q);
    } catch (err) {
      if (err.name === "AbortError") return;
      console.error(err);
      out.innerHTML = `<p class="hint">Error: ${err.message || err}</p>`;
    }
  };

  btn.addEventListener("click", run);
  input.addEventListener("keydown", (e) => { if (e.key === "Enter") run(); });
  // Optional: live search after a pause
  // input.addEventListener('input', debounce(run, 500));
  window._extSearch = run;
}

// -----------------------------------------------------
// Delete one local exercise
// -----------------------------------------------------
async function deleteExercise(id) {
  const res = await apiFetch(`/api/exercises/${id}`, { method: "DELETE" });
  if (res.status === 204) return { status: "deleted" };

  if (res.status === 409) {
    try {
      const usageRes = await apiFetch(`/api/exercises/${id}/usage`);
      if (usageRes.ok) {
        const usage = await usageRes.json();
        return { status: "in_use", usage };
      }
    } catch (e) {
      console.error("usage fetch failed", e);
    }
    return {
      status: "in_use",
      usage: { exercise: { id, name: "This exercise" }, workouts: [], sessions: [], counts: { workouts: 0, sessions: 0 } }
    };
  }

  const txt = await res.text().catch(() => "");
  return { status: "error", message: txt || `Delete failed (${res.status})` };
}

// -----------------------------------------------------
// Import from external
// -----------------------------------------------------
async function importExternal(obj) {
  const res = await apiFetch("/api/external/exercises/import", {
    method: "POST",
    body: JSON.stringify(obj),
  });
  if (!res.ok) {
    const txt = await res.text().catch(() => "");
    throw new Error(`Import failed ${res.status}: ${txt || res.statusText}`);
  }
  return res.json();
}

// -----------------------------------------------------
// Local exercises table
// -----------------------------------------------------
async function fetchLocalExercises() {
  const q = (el("ex-q") && el("ex-q").value ? el("ex-q").value : "").trim();
  const cat = (el("ex-cat-filter") && el("ex-cat-filter").value ? el("ex-cat-filter").value : "").trim();

  const params = new URLSearchParams();
  if (q) params.set("q", q);
  if (cat) params.set("category", cat);
  params.set("limit", "100");

  const res = await apiFetch(`/api/exercises?${params.toString()}`);
  if (!res.ok) return;
  const rows = await res.json();

  // ensure stable order
  rows.sort((a, b) => a.id - b.id);
  renderLocalExercises(rows);
}

function renderLocalExercises(rows) {
  const tbody = document.querySelector("#ex-table tbody");
  if (!tbody) return;
  tbody.innerHTML = rows.map((r, i) => `
    <tr data-id="${r.id}">
      <td>${i + 1}</td>
      <td>${r.name}</td>
      <td>${r.category ? `<span class="badge">${r.category}</span>` : ""}</td>
      <td>${r.default_unit || ""}</td>
      <td class="right">
        <button type="button" class="warn ex-del" data-id="${r.id}">Delete</button>
      </td>
    </tr>`).join("");
}

function wireLocalFilters() {
  const q = el("ex-q");
  const cat = el("ex-cat-filter");
  if (q) q.addEventListener("input", debounce(fetchLocalExercises, 250));
  if (cat) cat.addEventListener("input", debounce(fetchLocalExercises, 250));
}

// -----------------------------------------------------
// Browse-by-muscle (manual)
// -----------------------------------------------------
async function fetchMuscles() {
  try {
    const res = await apiFetch("/api/external/muscles");
    const list = await res.json();
    const sel = el("browse-muscle");
    if (sel && Array.isArray(list)) {
      list.forEach(m => {
        const opt = document.createElement("option");
        opt.value = m.slug;
        opt.textContent = m.label;
        sel.appendChild(opt);
      });
    }
  } catch (_) {}
}

async function browseExternalFetch({ muscle, limit, offset }) {
  const key = `${muscle || "all"}|${limit}|${offset}`;
  if (_cache.browse.has(key)) return _cache.browse.get(key);

  if (_aborters.browse) _aborters.browse.abort();
  _aborters.browse = new AbortController();

  const params = new URLSearchParams();
  if (muscle) params.set("muscle", muscle);
  params.set("limit", String(limit));
  params.set("offset", String(offset));

  const res = await apiFetch(`/api/external/exercises/browse?${params.toString()}`, {
    signal: _aborters.browse.signal
  });
  if (!res.ok) throw new Error(`Browse failed ${res.status}`);
  const data = await res.json();
  const items = data && data.items ? data.items : [];
  _cache.browse.set(key, items);
  return items;
}

async function browseExternal(reset = false) {
  if (_browseState.loading) return;
  _browseState.loading = true;

  const cont = el("browse-results");
  if (reset) cont.innerHTML = "";
  setLoading(cont, "Loading…");
  if (reset) _browseState.offset = 0;

  try {
    const items = await browseExternalFetch({
      muscle: _browseState.muscle || null,
      limit: _browseState.limit,
      offset: _browseState.offset,
    });

    if (reset) cont.innerHTML = "";
    renderBrowseResults(items, !!reset);
    _browseState.offset += _browseState.limit;

    const loadMore = el("browse-more");
    if (loadMore) loadMore.disabled = items.length < _browseState.limit;
  } catch (err) {
    if (err.name !== "AbortError") {
      console.error(err);
      cont.innerHTML = `<p class="hint">Error: ${err.message || err}</p>`;
    }
  } finally {
    _browseState.loading = false;
  }
}

function renderBrowseResults(items, firstPage) {
  const cont = el("browse-results");
  if (!cont) return;

  if (firstPage && !items.length) {
    cont.innerHTML = '<p class="hint">No items found.</p>';
    return;
  }

  items.forEach(item => {
    const card = document.createElement("div");
    card.className = "card";
    card.style.marginTop = "8px";

    const prim = (item.muscles && item.muscles.primary ? item.muscles.primary : []).join(", ");
    const sec  = (item.muscles && item.muscles.secondary ? item.muscles.secondary : []).join(", ");
    const muscles = (prim || sec) ? ` • muscles: ${prim}${sec ? ` (sec: ${sec})` : ""}` : "";

    const uid = `bimp-${Date.now()}-${Math.random().toString(36).slice(2)}`;
    card.innerHTML = `
      <div style="display:flex;justify-content:space-between;align-items:center;gap:12px">
        <div>
          <div style="font-weight:700">${item.name}</div>
          <div class="hint">${item.category || ""}${muscles}</div>
        </div>
        <button type="button" class="primary" id="${uid}">Import</button>
      </div>`;
    cont.appendChild(card);

    const btn = card.querySelector("#" + uid);
    if (btn) {
      btn.addEventListener("click", async () => {
        try {
          const saved = await importExternal(item);
          alert(`Imported: ${saved.name}`);
          await fetchLocalExercises();
        } catch (err) {
          console.error(err);
          alert(err.message || "Import failed");
        }
      });
    }
  });
}

function attachBrowseHandlers() {
  const sel  = el("browse-muscle");
  const btn  = el("browse-btn");
  const more = el("browse-more");
  if (!sel || !btn || !more) return;

  sel.addEventListener("change", () => {
    _browseState.muscle = sel.value || "";
  });

  btn.addEventListener("click", () => {
    if (!_browseState.muscle) {
      const r = el("browse-results");
      if (r) r.innerHTML = '<p class="hint">Pick a muscle first.</p>';
      more.disabled = true;
      return;
    }
    browseExternal(true);
  });

  more.addEventListener("click", () => {
    browseExternal(false);
  });
}

// -----------------------------------------------------
// Tabs (Search | Browse) + boot
// -----------------------------------------------------
function attachTabs() {
  const tabSearch = el("tab-search");
  const tabBrowse = el("tab-browse");
  const paneSearch = el("pane-search");
  const paneBrowse = el("pane-browse");
  if (!tabSearch || !tabBrowse || !paneSearch || !paneBrowse) return;

  const activate = (which) => {
    tabSearch.classList.toggle("active", which === "search");
    tabBrowse.classList.toggle("active", which === "browse");
    paneSearch.classList.toggle("active", which === "search");
    paneBrowse.classList.toggle("active", which === "browse");
  };

  tabSearch.addEventListener("click", () => activate("search"));
  tabBrowse.addEventListener("click", () => activate("browse"));
  activate("search");
}

document.addEventListener("DOMContentLoaded", () => {
  attachTabs();
  attachExploreHandlers();
  wireLocalFilters();
  fetchLocalExercises();
  fetchMuscles();
  attachBrowseHandlers();
  attachAddExerciseHandler();
});

// Delete button delegation
document.addEventListener("click", async (e) => {
  const btn = e.target && e.target.closest ? e.target.closest(".ex-del") : null;
  if (!btn) return;

  const id = btn.getAttribute("data-id");
  if (!id) return;

  if (!confirm("Delete this exercise? This will fail if it is used in a workout or session.")) return;

  const result = await deleteExercise(id);
  if (result.status === "deleted") {
    const tr = document.querySelector(`#ex-table tbody tr[data-id="${id}"]`);
    if (tr) tr.remove();
    return;
  }
  if (result.status === "in_use") {
    showUsageModal(result.usage);
    return;
  }
  alert(result.message || "Delete failed");
});