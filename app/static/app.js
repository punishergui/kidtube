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

function buildAdminPinModal() {
  if (document.getElementById('admin-pin-overlay')) return;
  const overlay = document.createElement('div');
  overlay.id = 'admin-pin-overlay';
  overlay.className = 'pin-overlay';
  overlay.setAttribute('aria-hidden', 'true');
  overlay.innerHTML = `
    <div class="pin-modal panel" role="dialog" aria-modal="true" aria-labelledby="admin-pin-title">
      <h2 id="admin-pin-title">Admin Access</h2>
      <p class="pin-subtitle">Enter your PIN</p>
      <div id="admin-pin-dots" class="pin-dots" aria-live="polite">
        <span class="pin-dot"></span><span class="pin-dot"></span><span class="pin-dot"></span><span class="pin-dot"></span><span class="pin-dot"></span><span class="pin-dot"></span>
      </div>
      <p id="admin-pin-error" class="pin-error-msg" hidden>Incorrect PIN</p>
      <div id="admin-pin-keypad" class="pin-keypad">
        <button type="button" data-key="1">1</button><button type="button" data-key="2">2</button><button type="button" data-key="3">3</button>
        <button type="button" data-key="4">4</button><button type="button" data-key="5">5</button><button type="button" data-key="6">6</button>
        <button type="button" data-key="7">7</button><button type="button" data-key="8">8</button><button type="button" data-key="9">9</button>
        <span></span><button type="button" data-key="0">0</button><button type="button" data-action="backspace">⌫</button>
      </div>
      <button id="admin-pin-cancel" type="button" class="btn-secondary">Cancel</button>
    </div>`;
  document.body.appendChild(overlay);
}

function initAdminAccess() {
  buildAdminPinModal();
  const overlay = document.getElementById('admin-pin-overlay');
  const dots = document.getElementById('admin-pin-dots');
  const keypad = document.getElementById('admin-pin-keypad');
  const cancel = document.getElementById('admin-pin-cancel');
  const error = document.getElementById('admin-pin-error');
  let digits = [];
  let pinLength = 4;
  let submitting = false;

  const setVisible = (open) => {
    overlay.style.display = open ? 'flex' : 'none';
    overlay.setAttribute('aria-hidden', open ? 'false' : 'true');
  };
  const updateDots = () => {
    dots.querySelectorAll('.pin-dot').forEach((dot, index) => dot.classList.toggle('filled', index < digits.length));
  };
  const clear = () => {
    digits = [];
    error.hidden = true;
    dots.classList.remove('shake');
    updateDots();
  };
  const fail = () => {
    error.hidden = false;
    dots.classList.remove('shake');
    void dots.offsetWidth;
    dots.classList.add('shake');
    digits = [];
    updateDots();
  };

  const verify = async () => {
    if (submitting || digits.length < pinLength) return;
    submitting = true;
    try {
      await requestJson('/api/session/admin-verify', { method: 'POST', body: JSON.stringify({ pin: digits.join('') }) });
      window.location.href = '/admin';
    } catch {
      fail();
    } finally {
      submitting = false;
    }
  };

  keypad?.addEventListener('click', (event) => {
    const button = event.target.closest('button');
    if (!button) return;
    if (button.dataset.action === 'backspace') {
      digits.pop();
      updateDots();
      return;
    }
    const key = button.dataset.key;
    if (!key || digits.length >= 6) return;
    error.hidden = true;
    digits.push(key);
    updateDots();
    if (digits.length >= pinLength) void verify();
  });

  cancel?.addEventListener('click', () => {
    clear();
    setVisible(false);
  });
  window.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && overlay.getAttribute('aria-hidden') === 'false') {
      clear();
      setVisible(false);
    }
  });

  document.querySelectorAll('.js-admin-link').forEach((link) => {
    link.addEventListener('click', async (event) => {
      try {
        const sessionState = await requestJson('/api/session');
        if (!sessionState?.kid_id) return;
        event.preventDefault();
        const status = await requestJson('/api/session/admin-pin');
        if (!status?.is_set) {
          window.location.href = '/admin';
          return;
        }
        pinLength = 4;
        clear();
        setVisible(true);
      } catch (error) {
        showToast(`Admin access denied: ${error.message}`, 'error');
      }
    });
  });
}

setActiveNav();
initHeaderSearch();
initProfileMenu();
initAdminAccess();
