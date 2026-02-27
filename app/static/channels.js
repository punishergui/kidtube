import { formatDate, requestJson, showToast } from '/static/app.js';

const body = document.getElementById('channels-body');
const form = document.getElementById('channel-lookup-form');
const preview = document.getElementById('channel-preview');

let latestLookup = null;

function escapeHtml(value) {
  return String(value || '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}

function row(channel) {
  return `
    <article class="panel admin-card">
      <div class="admin-card-head">
        <h3>${channel.title || 'Untitled channel'}</h3>
        <span class="small">${channel.youtube_id}</span>
      </div>
      <p class="small">Input: ${channel.input || '—'}</p>
      <p class="small">Resolve: ${channel.resolve_status}${channel.resolve_error ? ` · ${channel.resolve_error}` : ''}</p>

      <div class="switch-row">
        <label class="switch-field">
          <span>Allowed</span>
          <input type="checkbox" data-id="${channel.id}" data-action="allowed" ${channel.allowed ? 'checked' : ''} />
          <span class="slider"></span>
        </label>
        <label class="switch-field">
          <span>Enabled</span>
          <input type="checkbox" data-id="${channel.id}" data-action="enabled" ${channel.enabled ? 'checked' : ''} />
          <span class="slider"></span>
        </label>
        <label class="switch-field">
          <span>Blocked</span>
          <input type="checkbox" data-id="${channel.id}" data-action="blocked" ${channel.blocked ? 'checked' : ''} />
          <span class="slider"></span>
        </label>
      </div>

      <div class="reason-row">
        <input data-reason="${channel.id}" value="${channel.blocked_reason || ''}" placeholder="Blocked reason" />
        <button class="btn-soft" data-save-reason="${channel.id}">Save reason</button>
      </div>
      <p class="small">Last sync: ${formatDate(channel.last_sync)}</p>
    </article>
  `;
}

function renderLookupPreview(payload) {
  if (!payload?.found || !payload.channel) {
    preview.hidden = false;
    preview.innerHTML = `
      <h2>Nothing found</h2>
      <p class="small">${escapeHtml(payload?.error || 'Try a different handle, channel ID, or channel URL.')}</p>
    `;
    latestLookup = null;
    return;
  }

  const channel = payload.channel;
  const videos = (payload.sample_videos || [])
    .map(
      (video) => `
      <a class="sample-video" href="/watch/${video.youtube_id}" target="_blank" rel="noopener noreferrer">
        <img src="${video.thumbnail_url}" alt="${escapeHtml(video.title)}" />
        <span>${escapeHtml(video.title)}</span>
      </a>`,
    )
    .join('');

  preview.hidden = false;
  preview.innerHTML = `
    <div class="channel-preview-head">
      ${channel.avatar_url ? `<img class="avatar preview-avatar" src="${channel.avatar_url}" alt="" />` : ''}
      <div>
        <h2>${escapeHtml(channel.title || 'Untitled channel')}</h2>
        <p class="small">${escapeHtml(channel.handle || '')} · ${escapeHtml(channel.youtube_id)}</p>
      </div>
    </div>
    <p class="small clamp-text">${escapeHtml(channel.description || 'No description available.')}</p>
    <p class="small">Subscribers: ${channel.subscriber_count ?? '—'} · Videos: ${channel.video_count ?? '—'}</p>
    <h3>Recent samples</h3>
    <div class="sample-grid">${videos || '<p class="small">No sample videos returned.</p>'}</div>
    <div class="preview-actions">
      <button class="btn-primary" id="add-channel-btn">Add Channel</button>
      <button class="btn-soft" id="block-channel-btn">Block Channel</button>
    </div>
  `;

  latestLookup = payload;

  document.getElementById('add-channel-btn')?.addEventListener('click', () => submitFromPreview(false));
  document.getElementById('block-channel-btn')?.addEventListener('click', () => submitFromPreview(true));
}

async function submitFromPreview(blocked) {
  if (!latestLookup?.query) {
    showToast('Search and preview a channel before adding it.', 'error');
    return;
  }

  const data = new FormData(form);
  const category = String(data.get('category') || '').trim() || null;

  try {
    const created = await requestJson('/api/channels', {
      method: 'POST',
      body: JSON.stringify({ input: latestLookup.query, category }),
    });

    if (blocked) {
      await requestJson(`/api/channels/${created.id}`, {
        method: 'PATCH',
        body: JSON.stringify({ blocked: true, allowed: false, blocked_reason: 'Blocked by admin review' }),
      });
      showToast('Channel blocked.');
    } else {
      showToast('Channel added.');
    }

    await loadChannels();
  } catch (error) {
    showToast(`Unable to save channel: ${error.message}`, 'error');
  }
}

async function patchChannel(id, payload) {
  await requestJson(`/api/channels/${id}`, { method: 'PATCH', body: JSON.stringify(payload) });
  showToast('Channel updated.');
  await loadChannels();
}

async function loadChannels() {
  const channels = await requestJson('/api/channels');

  if (!channels.length) {
    body.innerHTML = '<article class="panel empty-state">No channels yet. Use search + preview to add one.</article>';
    return;
  }

  body.innerHTML = channels.map(row).join('');

  body.querySelectorAll('input[data-action]').forEach((input) => {
    input.addEventListener('change', async () => {
      const id = Number(input.dataset.id);
      const action = input.dataset.action;
      const channel = channels.find((item) => item.id === id);
      let payload;
      if (action === 'allowed') payload = { allowed: !channel.allowed };
      if (action === 'enabled') payload = { enabled: !channel.enabled };
      if (action === 'blocked') {
        const reason = body.querySelector(`input[data-reason="${id}"]`)?.value?.trim();
        payload = { blocked: !channel.blocked, blocked_reason: reason || null };
      }

      try {
        await patchChannel(id, payload);
      } catch (error) {
        showToast(`Update failed: ${error.message}`, 'error');
      }
    });
  });

  body.querySelectorAll('button[data-save-reason]').forEach((button) => {
    button.addEventListener('click', async () => {
      const id = Number(button.dataset.saveReason);
      const reason = body.querySelector(`input[data-reason="${id}"]`)?.value?.trim() || null;
      try {
        await patchChannel(id, { blocked_reason: reason });
      } catch (error) {
        showToast(`Reason save failed: ${error.message}`, 'error');
      }
    });
  });
}

form.addEventListener('submit', async (event) => {
  event.preventDefault();
  const query = String(new FormData(form).get('query') || '').trim();
  if (!query) return;

  try {
    const response = await requestJson(`/api/channel-lookup?query=${encodeURIComponent(query)}`);
    renderLookupPreview(response);
  } catch (error) {
    showToast(`Lookup failed: ${error.message}`, 'error');
  }
});

loadChannels().catch((error) => showToast(`Unable to load channels: ${error.message}`, 'error'));
