document.addEventListener('DOMContentLoaded', () => {
  const $ = s => document.querySelector(s);
  const tbody = document.querySelector('#ex-table tbody');

  const load = async () => {
    const q = $('#ex-q').value.trim();
    const category = $('#ex-cat-filter').value.trim();
    const params = new URLSearchParams();
    if (q) params.set('q', q);
    if (category) params.set('category', category);

    const res = await fetch(`/api/exercises?${params}`);
    const data = await res.json();
    tbody.innerHTML = data.map(e => `
      <tr>
        <td>${e.id}</td>
        <td>${e.name}</td>
        <td><span class="badge">${e.category}</span></td>
        <td>${e.unit || ''}</td>
      </tr>
    `).join('');
  };

  document.getElementById('btn-add-exercise').addEventListener('click', async () => {
    const body = {
      name: $('#ex-name').value.trim(),
      category: $('#ex-category').value.trim(),
      unit: $('#ex-unit').value.trim()
    };
    if (!body.name || !body.category) {
      alert('Name and category are required');
      return;
    }
    const res = await fetch('/api/exercises', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(body)
    });
    if (!res.ok) {
      const err = await res.json().catch(()=>({error:'Failed'}));
      alert(err.error || 'Failed to add');
      return;
    }
    $('#ex-name').value = '';
    $('#ex-category').value = '';
    $('#ex-unit').value = '';
    load();
  });

  $('#ex-q').addEventListener('input', load);
  $('#ex-cat-filter').addEventListener('input', load);
  load();
});