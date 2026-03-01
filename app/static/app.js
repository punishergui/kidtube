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

function initAdminAccess() {
  const modal = document.getElementById('admin-pin-modal');
  const dotsWrap = document.getElementById('pin-dots');
  const numpad = document.getElementById('pin-numpad');
  const error = document.getElementById('pin-error');
  const cancel = document.getElementById('pin-cancel');
  if (!modal || !dotsWrap || !numpad || !cancel || !error) return;

  const links = document.querySelectorAll('.js-admin-link');
  let pinBuffer = '';
  let pinLength = 4;
  let submitting = false;

  const reset = () => {
    pinBuffer = '';
    error.hidden = true;
    dotsWrap.classList.remove('shake');
    dotsWrap.querySelectorAll('.pin-dot').forEach((dot) => dot.classList.remove('filled'));
  };

  const renderDots = () => {
    dotsWrap.querySelectorAll('.pin-dot').forEach((dot, idx) => {
      dot.classList.toggle('filled', idx < pinBuffer.length);
    });
  };

  const close = () => {
    modal.hidden = true;
    reset();
  };

  const fail = () => {
    error.hidden = false;
    dotsWrap.classList.remove('shake');
    void dotsWrap.offsetWidth;
    dotsWrap.classList.add('shake');
    pinBuffer = '';
    renderDots();
  };

  const submit = async () => {
    if (submitting || pinBuffer.length < pinLength) return;
    submitting = true;
    try {
      await requestJson('/api/session/admin-verify', {
        method: 'POST',
        body: JSON.stringify({ pin: pinBuffer }),
      });
      close();
      window.location.href = '/admin';
    } catch {
      fail();
    } finally {
      submitting = false;
    }
  };

  links.forEach((link) => link.addEventListener('click', async (event) => {
    event.preventDefault();
    try {
      const pinStatus = await requestJson('/api/session/admin-pin');
      if (!pinStatus?.is_set) {
        window.location.href = '/admin';
        return;
      }
      reset();
      pinLength = 4;
      modal.hidden = false;
    } catch {
      window.location.href = '/admin';
    }
  }));

  numpad.addEventListener('click', (event) => {
    const button = event.target.closest('button');
    if (!button || modal.hidden) return;
    if (button.dataset.action === 'backspace') {
      pinBuffer = pinBuffer.slice(0, -1);
      renderDots();
      return;
    }
    const key = button.dataset.key;
    if (!key || pinBuffer.length >= 6) return;
    error.hidden = true;
    pinBuffer += key;
    renderDots();
    if (pinBuffer.length === 4 || pinBuffer.length === 6) {
      void submit();
    }
  });

  cancel.addEventListener('click', close);

  window.addEventListener('keydown', (event) => {
    if (!modal.hidden && event.key === 'Escape') {
      close();
    }
  });
}

setActiveNav();
initHeaderSearch();
initProfileMenu();
initAdminAccess();
