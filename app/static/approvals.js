import { formatDate, requestJson, showToast } from '/static/app.js';

const list = document.getElementById('approvals-list');
const tabs = Array.from(document.querySelectorAll('[data-status-tab]'));
let activeStatus = 'pending';

function renderRows(rows) {
  if (!rows.length) {
    list.innerHTML = '<article class="empty-state panel">No requests.</article>';
    return;
  }
  list.innerHTML = rows.map((row) => `
    <article class="panel" data-request-id="${row.id}" style="margin-bottom:0.5rem;">
      <div style="display:flex;justify-content:space-between;gap:0.75rem;flex-wrap:wrap;align-items:center;">
        <div>
          <div><strong>${row.requested_by_kid_name || 'Unknown kid'}</strong> requested <strong>${row.title || row.video_id || row.channel_id || 'item'}</strong></div>
          <div class="small">${row.type} · ${formatDate(row.created_at)}</div>
        </div>
        <div style="display:flex;gap:0.35rem;">
          ${activeStatus === 'pending' ? `<button class="btn-primary" data-approve="${row.id}">Approve</button><button class="btn-secondary" data-deny="${row.id}">Deny</button>` : `<span class="small">${row.status}</span>`}
        </div>
      </div>
    </article>
  `).join('');

  list.querySelectorAll('[data-approve]').forEach((button) => button.addEventListener('click', async () => {
    await requestJson(`/api/requests/${button.dataset.approve}/approve`, { method: 'POST' });
    showToast('Approved');
    await load();
  }));

  list.querySelectorAll('[data-deny]').forEach((button) => button.addEventListener('click', async () => {
    await requestJson(`/api/requests/${button.dataset.deny}/deny`, { method: 'POST' });
    showToast('Denied');
    await load();
  }));
}

async function load() {
  tabs.forEach((tab) => tab.classList.toggle('btn-primary', tab.dataset.statusTab === activeStatus));
  const rows = await requestJson(`/api/requests?status=${activeStatus}`);
  renderRows(rows);
}

tabs.forEach((tab) => tab.addEventListener('click', async () => {
  activeStatus = tab.dataset.statusTab;
  await load();
}));

load().catch((error) => showToast(`Unable to load approvals: ${error.message}`, 'error'));
