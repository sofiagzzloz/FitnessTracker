document.addEventListener('DOMContentLoaded', () => {
  const $ = s => document.querySelector(s);

  const tSelect = $('#t-select'); // kept hidden but used by existing logic
  const tList = document.querySelector('#t-list');
  const tiExercise = $('#ti-exercise');
  const itemsTbody = document.querySelector('#template-items tbody');
  const activeName = document.querySelector('#active-workout-name');
  const activeNotes = document.querySelector('#active-workout-notes');

  const loadTemplates = async (selectIdToKeep) => {
    try {
      const res = await fetch('/api/workouts/templates');
      if (!res.ok) throw new Error('Failed to load templates');
      const templates = await res.json();
      const opts = ['<option value=""></option>'].concat(templates.map(t => `<option value="${t.id}">${t.name}</option>`));
      tSelect.innerHTML = opts.join('');
      // render chips
      tList.innerHTML = templates.map(t => {
        const notes = (t.notes || '').replace(/"/g, '&quot;');
        return `<button class="chip" data-id="${t.id}" data-notes="${notes}">${t.name}</button>`;
      }).join('');
      // activate current
      const activate = (id) => {
        tSelect.value = String(id);
        Array.from(tList.querySelectorAll('.chip')).forEach(el => {
          el.classList.toggle('active', el.getAttribute('data-id') === String(id));
        });
        const chip = tList.querySelector(`.chip[data-id="${id}"]`);
        if (activeName) activeName.textContent = chip ? chip.textContent : '—';
        if (activeNotes) activeNotes.textContent = chip ? (chip.getAttribute('data-notes') || '') : '';
      };
      tList.querySelectorAll('.chip').forEach(el => {
        el.addEventListener('click', () => { activate(el.getAttribute('data-id')); loadTemplateItems(); });
      });
      if (templates.length === 0){ itemsTbody.innerHTML = ''; return; }
      if (selectIdToKeep){ activate(selectIdToKeep); } else { activate(templates[0].id); }
      loadTemplateItems();
    } catch(err){
      alert(err.message || 'Error loading templates');
    }
  };

  const loadExercisesForSelect = async () => {
    try {
      const res = await fetch('/api/_exercises_for_select');
      if (!res.ok) throw new Error('Failed to load exercises');
      const items = await res.json();
      const opts = ['<option value="">— Select —</option>']
        .concat(items.map(e => `<option value="${e.id}">${e.name}</option>`));
      tiExercise.innerHTML = opts.join('');
    } catch(err){
      alert(err.message || 'Error loading exercises');
    }
  };

  const loadTemplateItems = async () => {
    const templateId = tSelect.value;
    if (!templateId){ itemsTbody.innerHTML = ''; return; }
    try {
      const res = await fetch(`/api/workouts/templates/${templateId}/items`);
      if (!res.ok) throw new Error('Failed to load template items');
      const items = await res.json();
      itemsTbody.innerHTML = items.map(i => `
        <tr>
          <td>${i.id}</td>
          <td class="right">${i.order}</td>
          <td>${i.exercise_name}</td>
          <td><input class="ti-edit-planned" data-id="${i.id}" value="${(i.planned||'').replace(/"/g,'&quot;')}"></td>
          <td><input class="ti-edit-notes" data-id="${i.id}" value="${(i.notes||'').replace(/"/g,'&quot;')}"></td>
          <td class="right">
            <button class="ti-save" data-id="${i.id}">Save</button>
            <button class="ti-delete warn" data-id="${i.id}">Delete</button>
          </td>
        </tr>
      `).join('');

      itemsTbody.querySelectorAll('.ti-save').forEach(btn => {
        btn.addEventListener('click', async () => {
          const templateId = tSelect.value;
          const itemId = btn.getAttribute('data-id');
          const planned = itemsTbody.querySelector(`.ti-edit-planned[data-id="${itemId}"]`).value;
          const notes = itemsTbody.querySelector(`.ti-edit-notes[data-id="${itemId}"]`).value;
          try{
            const res = await fetch(`/api/workouts/templates/${templateId}/items/${itemId}`, {
              method: 'PUT', headers: {'Content-Type':'application/json'},
              body: JSON.stringify({ planned, notes })
            });
            if (!res.ok) throw new Error('Failed to save');
            await loadTemplateItems();
          } catch(err){
            alert(err.message || 'Error saving');
          }
        });
      });

      itemsTbody.querySelectorAll('.ti-delete').forEach(btn => {
        btn.addEventListener('click', async () => {
          if (!confirm('Delete this exercise from the workout?')) return;
          const templateId = tSelect.value;
          const itemId = btn.getAttribute('data-id');
          try{
            const res = await fetch(`/api/workouts/templates/${templateId}/items/${itemId}`, { method: 'DELETE' });
            if (!res.ok) throw new Error('Failed to delete');
            await loadTemplateItems();
          } catch(err){
            alert(err.message || 'Error deleting');
          }
        });
      });
    } catch(err){
      alert(err.message || 'Error loading items');
    }
  };

  $('#btn-create-template').addEventListener('click', async () => {
    const name = ($('#t-name').value || '').trim();
    const notes = ($('#t-notes').value || '').trim();
    if (!name){ alert('Name is required'); return; }
    try {
      const res = await fetch('/api/workouts/templates', {
        method: 'POST', headers: {'Content-Type':'application/json'},
        body: JSON.stringify({ name, notes })
      });
      if (!res.ok){
        let err; try { err = await res.json(); } catch { err = { error: 'Failed' } }
        throw new Error(err.error || 'Failed to create');
      }
      const created = await res.json();
      $('#t-name').value = '';
      $('#t-notes').value = '';
      await loadTemplates(created.id);
    } catch(err){
      alert(err.message || 'Error creating template');
    }
  });

  $('#btn-delete-template').addEventListener('click', async () => {
    const templateId = tSelect.value;
    if (!templateId){ alert('No template selected'); return; }
    if (!confirm('Delete this workout template?')) return;
    try {
      const res = await fetch(`/api/workouts/templates/${templateId}`, { method:'DELETE' });
      if (!res.ok){
        let err; try { err = await res.json(); } catch { err = { error: 'Failed' } }
        throw new Error(err.error || 'Failed to delete');
      }
      await loadTemplates();
    } catch(err){
      alert(err.message || 'Error deleting template');
    }
  });

  $('#btn-refresh-templates').addEventListener('click', loadTemplates);
  tSelect.addEventListener('change', loadTemplateItems);

  $('#btn-add-template-item').addEventListener('click', async () => {
    const templateId = tSelect.value;
    if (!templateId){ alert('Create or select a template first'); return; }
    const exercise_id = tiExercise.value;
    const planned = ($('#ti-planned').value || '').trim();
    const notes = ($('#ti-notes').value || '').trim();
    if (!exercise_id){ alert('Pick an exercise'); return; }
    try {
      const res = await fetch(`/api/workouts/templates/${templateId}/items`, {
        method: 'POST', headers: {'Content-Type':'application/json'},
        body: JSON.stringify({ exercise_id, planned, notes })
      });
      if (!res.ok){
        let err; try { err = await res.json(); } catch { err = { error: 'Failed' } }
        throw new Error(err.error || 'Failed to add');
      }
      $('#ti-planned').value = '';
      $('#ti-notes').value = '';
      await loadTemplateItems();
    } catch(err){
      alert(err.message || 'Error adding item');
    }
  });

  // Initial loads
  Promise.all([loadTemplates(), loadExercisesForSelect()]);
});

