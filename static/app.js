const $ = (sel) => document.querySelector(sel);
const API = {
  exercises: "/exercises",
  workouts: "/workouts"
};

async function fetchJSON(url, opts={}) {
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

init();