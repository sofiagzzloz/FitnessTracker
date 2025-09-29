function el(id){ return document.getElementById(id); }

document.getElementById('reg-form')?.addEventListener('submit', async (e) => {
  e.preventDefault();
  const email = el('reg-email').value.trim();
  const password = el('reg-pass').value;

  if (!email.includes('@')) { alert('Please enter a valid email.'); return; }
  if (!password || password.length < 6) { alert('Password must be at least 6 characters.'); return; }

  try {
    const res = await fetch('/api/auth/register', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({ email, password })
    });

    if (!res.ok) {
      const msg = await res.text().catch(()=>res.statusText);
      alert(msg || 'Registration failed');
      return;
    }

    // optional: auto-login or redirect to /login
    window.location.assign('/login');
  } catch (err) {
    alert(err?.message || 'Network error');
  }
});