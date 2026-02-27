import { formatDate, requestJson, showToast } from '/static/app.js';

const body = document.getElementById('channels-body');
const form = document.getElementById('add-channel-form');

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

async function patchChannel(id, payload) {
  await requestJson(`/api/channels/${id}`, { method: 'PATCH', body: JSON.stringify(payload) });
  showToast('Channel updated.');
  await loadChannels();
}

async function loadChannels() {
  const channels = await requestJson('/api/channels');

  if (!channels.length) {
    body.innerHTML = '<article class="panel empty-state">No channels yet. Add one above to get started.</article>';
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
  const data = new FormData(form);
  const payload = {
    input: String(data.get('input') || '').trim(),
    category: String(data.get('category') || '').trim() || null,
  };

  try {
    await requestJson('/api/channels', { method: 'POST', body: JSON.stringify(payload) });
    form.reset();
    showToast('Channel added.');
    await loadChannels();
  } catch (error) {
    showToast(`Unable to add channel: ${error.message}`, 'error');
  }
});

loadChannels().catch((error) => showToast(`Unable to load channels: ${error.message}`, 'error'));
