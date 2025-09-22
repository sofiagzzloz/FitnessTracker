document.addEventListener('DOMContentLoaded', () => {
  const $ = s => document.querySelector(s);

  const sSelect = $('#s-select');
  const siExercise = $('#si-exercise');
  const itemsTbody = document.querySelector('#items-table tbody');
  const sTemplate = document.querySelector('#s-template');

  const loadSessions = async (keepId) => {
    const res = await fetch('/api/sessions');
    const sessions = await res.json();
    sSelect.innerHTML = sessions.map(s => `<option value="${s.id}">${s.date} — ${s.title}</option>`).join('');
    if (sessions.length === 0){ itemsTbody.innerHTML = ''; return; }
    if (keepId){ sSelect.value = String(keepId); }
    loadSessionItems();
  };

  const loadExercisesForSelect = async () => {
    const res = await fetch('/api/_exercises_for_select');
    const items = await res.json();
    siExercise.innerHTML = items.map(e => `<option value="${e.id}">${e.name}</option>`).join('');
  };

  const loadTemplatesForSelect = async () => {
    if (!sTemplate) return;
    const res = await fetch('/api/_templates_for_select');
    const items = await res.json();
    sTemplate.innerHTML = items.map(t => `<option value="${t.id}">${t.name}</option>`).join('');
  };

  const loadSessionItems = async () => {
    const sessionId = sSelect.value;
    if (!sessionId){ itemsTbody.innerHTML = ''; return; }
    const res = await fetch(`/api/sessions/${sessionId}/items`);
    const items = await res.json();
    itemsTbody.innerHTML = items.map(i => `
      <tr>
        <td>${i.id}</td>
        <td class="right">${i.order}</td>
        <td>${i.exercise_name}</td>
        <td>${i.notes || ''}</td>
      </tr>
    `).join('');
  };

  $('#btn-create-session').addEventListener('click', async () => {
    const date = ($('#s-date').value || '').trim();
    const title = ($('#s-title').value || '').trim();
    const notes = ($('#s-notes').value || '').trim();
    if (!date || !title){ alert('Date and title are required'); return; }
    const res = await fetch('/api/sessions', {
      method: 'POST', headers: {'Content-Type':'application/json'},
      body: JSON.stringify({ date, title, notes })
    });
    if (!res.ok){
      const err = await res.json().catch(()=>({error:'Failed'}));
      alert(err.error || 'Failed to create');
      return;
    }
    const created = await res.json();
    $('#s-title').value = '';
    $('#s-notes').value = '';
    await loadSessions(created.id);
  });

  $('#btn-refresh-sessions').addEventListener('click', loadSessions);
  sSelect.addEventListener('change', loadSessionItems);

  $('#btn-add-item').addEventListener('click', async () => {
    const sessionId = sSelect.value;
    if (!sessionId){ alert('Create or select a session first'); return; }
    const exercise_id = siExercise.value;
    const orderRaw = ($('#si-order').value || '').trim();
    const notes = ($('#si-notes').value || '').trim();
    const body = { exercise_id };
    if (orderRaw) body.order = parseInt(orderRaw, 10);
    if (notes) body.notes = notes;
    const res = await fetch(`/api/sessions/${sessionId}/items`, {
      method: 'POST', headers: {'Content-Type':'application/json'},
      body: JSON.stringify(body)
    });
    if (!res.ok){
      const err = await res.json().catch(()=>({error:'Failed'}));
      alert(err.error || 'Failed to add');
      return;
    }
    $('#si-notes').value = '';
    $('#si-order').value = '';
    await loadSessionItems();
  });

  const createFromTemplateBtn = document.querySelector('#btn-create-from-template');
  if (createFromTemplateBtn){
    createFromTemplateBtn.addEventListener('click', async () => {
      const template_id = (sTemplate && sTemplate.value) || '';
      const date = ($('#st-date').value || '').trim();
      const title = ($('#st-title').value || '').trim();
      if (!template_id || !date){ alert('Template and date are required'); return; }
      const res = await fetch('/api/sessions/from_template', {
        method: 'POST', headers: {'Content-Type':'application/json'},
        body: JSON.stringify({ template_id, date, title })
      });
      if (!res.ok){
        const err = await res.json().catch(()=>({error:'Failed'}));
        alert(err.error || 'Failed to create');
        return;
      }
      const created = await res.json();
      await loadSessions(created.id);
    });
  }

  // Initial loads
  Promise.all([loadSessions(), loadExercisesForSelect(), loadTemplatesForSelect()]);
});

