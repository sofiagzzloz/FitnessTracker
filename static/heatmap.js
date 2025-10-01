// ========== MUSCLE MAP ==========

// Coordinates 
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
  
  // Heuristic fallbacks when DB has no links - Some basic exercises
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
    Object.keys(merged.primary).forEach(k => { delete merged.secondary[k]; });
    return merged;
  }

  let _lastSummary = null;
  
  function getCtx(which) { 
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
  
    const base = Math.min(w, h) * 0.10;
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
  
window.applyMapColors     = applyMapColors;
window.heatmapFallback    = buildFallbackSummary;
window.heatmapMerge       = mergeSummaries;