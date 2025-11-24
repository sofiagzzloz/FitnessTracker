import { API_BASE } from "./config.js";

function el(id) { return document.getElementById(id); }

// === REGISTRATION ===
document.getElementById('reg-form')?.addEventListener('submit', async (e) => {
  e.preventDefault();
  const email = el('reg-email').value.trim();
  const password = el('reg-pass').value;

  if (!email.includes('@')) { 
    alert('Please enter a valid email.'); 
    return; 
  }
  if (!password || password.length < 6) { 
    alert('Password must be at least 6 characters.'); 
    return; 
  }

  try {
    const res = await fetch(`${API_BASE}/api/auth/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({ email, password })
    });
    
    if (!res.ok) {
      const msg = await res.text().catch(() => res.statusText);
      alert(msg || 'Registration failed');
      return;
    }
    
    alert('Registration successful! Please login.');
    window.location.assign('/login');
  } catch (err) {
    alert(err?.message || 'Network error');
  }
});

// === LOGIN ===
document.getElementById('login-form')?.addEventListener('submit', async (e) => {
  e.preventDefault();
  const email = el('login-email').value.trim();
  const password = el('login-pass').value;

  if (!email || !password) {
    alert('Email and password are required');
    return;
  }

  try {
    const res = await fetch(`${API_BASE}/api/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({ email, password })
    });

    if (!res.ok) {
      const msg = await res.text().catch(() => res.statusText);
      alert(msg || 'Login failed');
      return;
    }

    const data = await res.json();
    
    // Store user info in localStorage
    localStorage.setItem('user', JSON.stringify({ email: data.email, id: data.id }));
    
    // Redirect to dashboard/root
    window.location.assign('/');
  } catch (err) {
    alert(err?.message || 'Network error');
  }
});

// === LOGOUT ===
async function logout() {
  try {
    await fetch(`${API_BASE}/logout`, {
      method: 'GET',
      credentials: 'include'
    });
    
    // Clear local storage
    localStorage.removeItem('user');
    
    // Redirect to login
    window.location.assign('/login');
  } catch (err) {
    console.error('Logout error:', err);
    // Force logout anyway
    localStorage.removeItem('user');
    window.location.assign('/login');
  }
}

// Make logout available globally
window.logout = logout;

// === CHECK AUTH STATUS ===
async function checkAuth() {
  try {
    const res = await fetch(`${API_BASE}/api/auth/me`, {
      credentials: 'include'
    });
    
    if (res.ok) {
      const user = await res.json();
      localStorage.setItem('user', JSON.stringify(user));
      return user;
    } else {
      localStorage.removeItem('user');
      return null;
    }
  } catch (err) {
    console.error('Auth check failed:', err);
    return null;
  }
}

// === PROTECT PAGES (call this on protected pages) ===
async function requireAuth() {
  const user = await checkAuth();
  
  if (!user) {
    // Not authenticated, redirect to login
    window.location.assign('/login');
    return null;
  }
  
  return user;
}

// Make functions available globally
window.checkAuth = checkAuth;
window.requireAuth = requireAuth;

// === UPDATE UI WITH USER INFO ===
function updateUserUI() {
  const userStr = localStorage.getItem('user');
  const userEmailEl = document.getElementById('user-email');
  
  if (userStr && userEmailEl) {
    try {
      const user = JSON.parse(userStr);
      userEmailEl.textContent = user.email || 'User';
    } catch (e) {
      console.error('Failed to parse user data:', e);
    }
  }
}

// Update UI on page load
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', updateUserUI);
} else {
  updateUserUI();
}
