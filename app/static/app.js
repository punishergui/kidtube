const pageContent = document.getElementById('page-content');
const alerts = document.getElementById('alerts');

const categoryOptions = ['education', 'music', 'science', 'cartoons', 'other'];

const routes = {
  '/': renderDashboard,
  '/dashboard': renderDashboard,
  '/channels': renderChannels,
  '/kids': renderKids,
  '/sync': renderSync,
};

function showAlert(message, type = 'success') {
  alerts.innerHTML = `<div class="status ${type}">${message}</div>`;
  setTimeout(() => {
    alerts.innerHTML = '';
  }, 3500);
}

function formatDate(value) {
  if (!value) return '—';
  return new Date(value).toLocaleString();
}

async function requestJson(url, options = {}) {
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

function setActiveNav(pathname) {
  document.querySelectorAll('.nav-link').forEach((link) => {
    link.classList.toggle('active', link.dataset.route === pathname || (pathname === '/dashboard' && link.dataset.route === '/'));
  });
}

async function navigate(pathname, push = true) {
  const renderer = routes[pathname] || renderDashboard;
  if (push) {
    window.history.pushState({}, '', pathname);
  }
  setActiveNav(pathname);
  await renderer();
}

async function renderDashboard() {
  const items = await requestJson('/api/feed/latest-per-channel');

  if (!items.length) {
    pageContent.innerHTML = '<h2>Dashboard</h2><p class="small">No videos yet. Run sync or allow channels to populate feed.</p>';
    return;
  }

  pageContent.innerHTML = `
    <h2>Dashboard</h2>
    <div class="card-grid">
      ${items
        .map(
          (item) => `
            <a class="video-card" target="_blank" rel="noopener" href="https://www.youtube.com/watch?v=${item.video_youtube_id}">
              <img class="thumb" src="${item.video_thumbnail_url}" alt="${item.video_title}" />
              <div class="video-card-body">
                <div class="channel-row">
                  <img class="avatar" src="${item.channel_avatar_url || ''}" alt="" />
                  <span>${item.channel_title || 'Unknown channel'}</span>
                </div>
                <h3>${item.video_title}</h3>
                <p class="small">Published ${formatDate(item.video_published_at)}</p>
              </div>
            </a>
          `,
        )
        .join('')}
    </div>
  `;
}

function channelRow(channel) {
  return `
    <tr>
      <td>${channel.id}</td>
      <td>${channel.title || '—'}</td>
      <td>${channel.input || '—'}</td>
      <td>${channel.youtube_id || '—'}</td>
      <td>${channel.category || '—'}</td>
      <td><button data-action="toggle-allowed" data-id="${channel.id}">${channel.allowed ? 'Disable' : 'Allow'}</button></td>
      <td><button data-action="toggle-enabled" data-id="${channel.id}">${channel.enabled ? 'Disable' : 'Enable'}</button></td>
      <td>
        <button data-action="toggle-blocked" data-id="${channel.id}">${channel.blocked ? 'Unblock' : 'Block'}</button>
        <input data-blocked-reason="${channel.id}" placeholder="blocked reason" value="${channel.blocked_reason || ''}" />
      </td>
      <td>${channel.resolve_status}</td>
      <td>${formatDate(channel.last_sync)}</td>
      <td>${channel.resolve_error ? `<details><summary>View error</summary><p>${channel.resolve_error}</p></details>` : '—'}</td>
    </tr>
  `;
}

async function renderChannels() {
  const channels = await requestJson('/api/channels');
  pageContent.innerHTML = `
    <h2>Channels</h2>
    <form id="add-channel-form">
      <input name="input" placeholder="@channel, channel ID, or URL" required />
      <select name="category">
        <option value="">Category (optional)</option>
        ${categoryOptions.map((option) => `<option value="${option}">${option}</option>`).join('')}
      </select>
      <button type="submit">Add Channel</button>
    </form>
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>id</th><th>title</th><th>input</th><th>youtube_id</th><th>category</th>
            <th>allowed</th><th>enabled</th><th>blocked</th><th>resolve_status</th><th>last_sync</th><th>resolve_error</th>
          </tr>
        </thead>
        <tbody>
          ${channels.map(channelRow).join('')}
        </tbody>
      </table>
    </div>
  `;

  document.getElementById('add-channel-form').addEventListener('submit', async (event) => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const payload = {
      input: String(form.get('input') || '').trim(),
      category: String(form.get('category') || '').trim() || null,
    };

    try {
      await requestJson('/api/channels', { method: 'POST', body: JSON.stringify(payload) });
      showAlert('Channel added successfully.');
      await renderChannels();
    } catch (error) {
      showAlert(`Unable to add channel: ${error.message}`, 'error');
    }
  });

  pageContent.querySelectorAll('button[data-action]').forEach((button) => {
    button.addEventListener('click', async () => {
      const id = Number(button.dataset.id);
      const action = button.dataset.action;
      const channel = channels.find((item) => item.id === id);
      let payload = {};

      if (action === 'toggle-allowed') payload = { allowed: !channel.allowed };
      if (action === 'toggle-enabled') payload = { enabled: !channel.enabled };
      if (action === 'toggle-blocked') {
        const reasonInput = pageContent.querySelector(`input[data-blocked-reason="${id}"]`);
        payload = {
          blocked: !channel.blocked,
          blocked_reason: String(reasonInput?.value || '').trim() || null,
        };
      }

      try {
        await requestJson(`/api/channels/${id}`, { method: 'PATCH', body: JSON.stringify(payload) });
        showAlert('Channel updated.');
        await renderChannels();
      } catch (error) {
        showAlert(`Unable to update channel: ${error.message}`, 'error');
      }
    });
  });
}

async function renderKids() {
  const kids = await requestJson('/api/kids');
  pageContent.innerHTML = `
    <h2>Kids</h2>
    <form id="add-kid-form">
      <input name="name" placeholder="Name" required />
      <input name="avatar_url" placeholder="Avatar URL (optional)" />
      <input name="daily_limit_minutes" type="number" min="1" placeholder="Daily limit minutes" />
      <button type="submit">Add Kid</button>
    </form>
    <div class="table-wrap">
      <table>
        <thead>
          <tr><th>id</th><th>name</th><th>avatar_url</th><th>daily_limit_minutes</th><th>created_at</th></tr>
        </thead>
        <tbody>
          ${kids
            .map(
              (kid) => `
                <tr>
                  <td>${kid.id}</td>
                  <td>${kid.name}</td>
                  <td>${kid.avatar_url || '—'}</td>
                  <td>${kid.daily_limit_minutes || '—'}</td>
                  <td>${formatDate(kid.created_at)}</td>
                </tr>
              `,
            )
            .join('')}
        </tbody>
      </table>
    </div>
  `;

  document.getElementById('add-kid-form').addEventListener('submit', async (event) => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const limitRaw = String(form.get('daily_limit_minutes') || '').trim();
    const payload = {
      name: String(form.get('name') || '').trim(),
      avatar_url: String(form.get('avatar_url') || '').trim() || null,
      daily_limit_minutes: limitRaw ? Number(limitRaw) : null,
    };

    try {
      await requestJson('/api/kids', { method: 'POST', body: JSON.stringify(payload) });
      showAlert('Kid created.');
      await renderKids();
    } catch (error) {
      showAlert(`Unable to create kid: ${error.message}`, 'error');
    }
  });
}

async function renderSync() {
  pageContent.innerHTML = `
    <h2>Sync</h2>
    <p class="small">Run an on-demand sync of enabled channels and refresh the dashboard feed.</p>
    <button id="run-sync">Run Sync</button>
    <div id="sync-result" class="sync-result">No sync run yet.</div>
  `;

  document.getElementById('run-sync').addEventListener('click', async () => {
    try {
      const result = await requestJson('/api/sync/run', { method: 'POST', body: '{}' });
      const failures = result.failures?.length
        ? `<ul>${result.failures.map((failure) => `<li>${failure.input || failure.id}: ${failure.error}</li>`).join('')}</ul>`
        : '<p>No failures.</p>';

      document.getElementById('sync-result').innerHTML = `
        <p><strong>channels_seen:</strong> ${result.channels_seen}</p>
        <p><strong>resolved:</strong> ${result.resolved}</p>
        <p><strong>synced:</strong> ${result.synced}</p>
        <p><strong>failed:</strong> ${result.failed}</p>
        <h3>Failures</h3>
        ${failures}
      `;
      showAlert('Sync completed.');
      await requestJson('/api/feed/latest-per-channel');
    } catch (error) {
      showAlert(`Sync failed: ${error.message}`, 'error');
    }
  });
}

window.addEventListener('popstate', () => {
  navigate(window.location.pathname, false);
});

document.querySelectorAll('a[data-route]').forEach((link) => {
  link.addEventListener('click', (event) => {
    event.preventDefault();
    navigate(link.dataset.route);
  });
});

navigate(window.location.pathname, false).catch((error) => {
  pageContent.innerHTML = `<p class="status error">Unable to load app: ${error.message}</p>`;
});
