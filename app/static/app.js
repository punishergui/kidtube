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

async function initSearchLogging() {
  const form = document.getElementById('header-search-form');
  const input = document.getElementById('header-search-input');
  if (!form || !input) return;

  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    const query = input.value.trim();
    if (!query) return;

    try {
      const sessionState = await requestJson('/api/session');
      if (!sessionState.kid_id) {
        showToast('Select a kid profile before searching.', 'error');
        return;
      }
      const results = await requestJson(`/api/search?q=${encodeURIComponent(query)}&kid_id=${sessionState.kid_id}`);
      window.dispatchEvent(new CustomEvent('kidtube:search-results', { detail: { query, results, kidId: sessionState.kid_id } }));
    } catch (error) {
      showToast(`Unable to search: ${error.message}`, 'error');
    }
  });
}

setActiveNav();
initSearchLogging();
