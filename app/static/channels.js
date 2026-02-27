import { formatDate, requestJson, showToast } from '/static/app.js';

const body = document.getElementById('channels-body');
const form = document.getElementById('add-channel-form');

function row(channel) {
  return `
    <tr>
      <td>${channel.title || '—'}</td>
      <td>${channel.input || '—'}</td>
      <td>${channel.youtube_id}</td>
      <td>${channel.resolve_status}${channel.resolve_error ? `<div class="small">${channel.resolve_error}</div>` : ''}</td>
      <td><button data-id="${channel.id}" data-action="allowed">${channel.allowed ? 'Allowed' : 'Blocked'}</button></td>
      <td><button data-id="${channel.id}" data-action="enabled">${channel.enabled ? 'Enabled' : 'Disabled'}</button></td>
      <td><button data-id="${channel.id}" data-action="blocked">${channel.blocked ? 'Blocked' : 'Not blocked'}</button></td>
      <td>
        <input data-reason="${channel.id}" value="${channel.blocked_reason || ''}" placeholder="Reason" />
        <div class="small">Last sync: ${formatDate(channel.last_sync)}</div>
      </td>
    </tr>
  `;
}

async function loadChannels() {
  const channels = await requestJson('/api/channels');
  body.innerHTML = channels.map(row).join('');

  body.querySelectorAll('button[data-action]').forEach((button) => {
    button.addEventListener('click', async () => {
      const id = Number(button.dataset.id);
      const action = button.dataset.action;
      const channel = channels.find((item) => item.id === id);
      let payload;
      if (action === 'allowed') payload = { allowed: !channel.allowed };
      if (action === 'enabled') payload = { enabled: !channel.enabled };
      if (action === 'blocked') {
        const reason = body.querySelector(`input[data-reason="${id}"]`)?.value?.trim();
        payload = { blocked: !channel.blocked, blocked_reason: reason || null };
      }

      try {
        await requestJson(`/api/channels/${id}`, { method: 'PATCH', body: JSON.stringify(payload) });
        showToast('Channel updated.');
        await loadChannels();
      } catch (error) {
        showToast(`Update failed: ${error.message}`, 'error');
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
