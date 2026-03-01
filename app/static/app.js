const alerts = document.getElementById('alerts');

export function showToast(message, type = 'success') {
  if (!alerts) return;
  alerts.innerHTML = `<div class="status ${type}">${message}</div>`;
  setTimeout(() => {
    alerts.innerHTML = '';
  }, 3500);
}

export function formatDate(value) {
  if (!value) return '—';
  return new Date(value).toLocaleString();
}

export async function requestJson(url, options = {}) {
  const response = await fetch(url, {
    headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
    ...options,
  });

  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = await response.json();
      detail = body.detail || JSON.stringify(body);
    } catch {
      detail = await response.text();
    }
    throw new Error(detail || `Request failed: ${response.status}`);
  }

  if (response.status === 204) return null;
  return response.json();
}

function setActiveNav() {
  const path = window.location.pathname;
  document.querySelectorAll('.nav-link').forEach((link) => {
    const route = link.dataset.route;
    const isRootMatch = route === '/' && (path === '/' || path === '/dashboard');
    link.classList.toggle('active', route === path || isRootMatch);
  });
}

function initHeaderSearch() {
  const form = document.getElementById('header-search-form');
  const input = document.getElementById('header-search-input');
  if (!form || !input) return;

  const isDashboard = window.location.pathname === '/dashboard' || window.location.pathname === '/';

  form.addEventListener('submit', (event) => {
    event.preventDefault();
    const query = input.value.trim();
    if (!query) {
      if (isDashboard) {
        window.dispatchEvent(new CustomEvent('kidtube:search-submit', { detail: { query: '' } }));
      }
      return;
    }

    if (!isDashboard) {
      window.location.href = `/dashboard?search=${encodeURIComponent(query)}`;
      return;
    }

    window.dispatchEvent(new CustomEvent('kidtube:search-submit', { detail: { query } }));
  });
}

function initProfileMenu() {
  document.getElementById('switch-profile')?.addEventListener('click', async () => {
    await fetch('/api/session/logout', { method: 'POST' });
    window.location = '/';
  });
}

setActiveNav();
initHeaderSearch();
initProfileMenu();
