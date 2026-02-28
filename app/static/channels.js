import { formatDate, requestJson, showToast } from '/static/app.js';

const body = document.getElementById('channels-body');
const form = document.getElementById('channel-lookup-form');
const preview = document.getElementById('channel-preview');
const filters = document.getElementById('channel-filters');
const categoriesBody = document.getElementById('categories-body');
const createCategoryForm = document.getElementById('create-category-form');
const categorySelect = document.getElementById('channel-category-select');

let latestLookup = null;
let allChannels = [];
let categories = [];
let activeFilter = 'all';

function escapeHtml(value) { return String(value || '').replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;').replaceAll('"', '&quot;').replaceAll("'", '&#39;'); }
function matchesFilter(channel) { if (activeFilter === 'whitelisted') return channel.allowed && !channel.blocked; if (activeFilter === 'blacklisted') return channel.blocked; if (activeFilter === 'disabled') return !channel.enabled; return true; }

function renderCategories() {
  categorySelect.innerHTML = '<option value="">Category (optional)</option>' + categories.filter((c) => c.enabled).map((category) => `<option value="${category.id}">${category.name}</option>`).join('');
  categoriesBody.innerHTML = categories.map((category) => `
    <article class="panel category-card">
      <div class="admin-card-head"><h3>${escapeHtml(category.name)}</h3><span class="left-pill ${category.enabled ? '' : 'pill-muted'}">${category.enabled ? 'Enabled' : 'Disabled'}</span></div>
      <p class="small">Default limit: ${category.daily_limit_minutes ?? 'none'} minutes/day</p>
      <div class="preview-actions">
        <button class="btn-soft" data-toggle-category="${category.id}">${category.enabled ? 'Disable' : 'Enable'}</button>
        <button class="btn-soft" data-edit-limit="${category.id}">Edit limit</button>
        <button class="btn-secondary" data-delete-category="${category.id}">Delete/Archive</button>
      </div>
    </article>
  `).join('') || '<article class="empty-state">No categories yet.</article>';

  categoriesBody.querySelectorAll('button[data-toggle-category]').forEach((button) => button.addEventListener('click', async () => {
    const id = Number(button.dataset.toggleCategory);
    const category = categories.find((item) => item.id === id);
    await requestJson(`/api/categories/${id}`, { method: 'PATCH', body: JSON.stringify({ enabled: !category.enabled }) });
    await loadCategories();
  }));

  categoriesBody.querySelectorAll('button[data-edit-limit]').forEach((button) => button.addEventListener('click', async () => {
    const id = Number(button.dataset.editLimit);
    const category = categories.find((item) => item.id === id);
    const value = window.prompt('Default daily minutes', String(category.daily_limit_minutes ?? ''));
    if (value === null) return;
    await requestJson(`/api/categories/${id}`, { method: 'PATCH', body: JSON.stringify({ daily_limit_minutes: value === '' ? null : Number(value) }) });
    await loadCategories();
  }));

  categoriesBody.querySelectorAll('button[data-delete-category]').forEach((button) => button.addEventListener('click', async () => {
    const id = Number(button.dataset.deleteCategory);
    try {
      await requestJson(`/api/categories/${id}?hard_delete=true`, { method: 'DELETE' });
      showToast('Category deleted.');
    } catch {
      await requestJson(`/api/categories/${id}?archive=true`, { method: 'DELETE' });
      showToast('Category archived (in use).');
    }
    await loadCategories();
  }));
}

function categoryDropdown(channel) {
  const options = ['<option value="">No category</option>']
    .concat(categories.map((category) => `<option value="${category.id}" ${channel.category_id === category.id ? 'selected' : ''}>${escapeHtml(category.name)}${category.enabled ? '' : ' (disabled)'}</option>`));
  return `<select data-category-for="${channel.id}">${options.join('')}</select>`;
}

function row(channel) {
  const status = channel.blocked ? 'Blocked' : (channel.allowed ? 'Allowed' : 'Pending');
  return `<article class="panel admin-card channel-card"><div class="admin-card-head"><h3>${escapeHtml(channel.title || 'Untitled channel')}</h3><span class="small">${escapeHtml(channel.youtube_id)}</span></div><p class="small">Input: ${escapeHtml(channel.input || '—')}</p><p class="small">Status: <strong>${status}</strong> · Last sync: ${formatDate(channel.last_sync)}</p><p class="small">Resolve: ${escapeHtml(channel.resolve_status)}${channel.resolve_error ? ` · ${escapeHtml(channel.resolve_error)}` : ''}</p><label class="small">Category ${categoryDropdown(channel)}</label><div class="preview-actions"><button class="btn-soft" data-allow="${channel.id}">Allow</button><button class="btn-soft" data-block="${channel.id}">Block</button><button class="btn-secondary" data-disable="${channel.id}">${channel.enabled ? 'Disable' : 'Enable'}</button><button class="btn-secondary" data-delete="${channel.id}">Remove</button></div></article>`;
}

function renderChannels() {
  const channels = allChannels.filter(matchesFilter);
  body.innerHTML = channels.length ? channels.map(row).join('') : '<article class="panel empty-state">No channels for this filter.</article>';
  body.querySelectorAll('select[data-category-for]').forEach((select) => select.addEventListener('change', async () => {
    const id = Number(select.dataset.categoryFor);
    const categoryId = Number(select.value || 0) || null;
    await requestJson(`/api/channels/${id}`, { method: 'PATCH', body: JSON.stringify({ category_id: categoryId }) });
    await loadChannels();
  }));
  body.querySelectorAll('button[data-allow]').forEach((button) => button.addEventListener('click', async () => {
    await requestJson(`/api/channels/${Number(button.dataset.allow)}`, { method: 'PATCH', body: JSON.stringify({ allowed: true, blocked: false, enabled: true }) });
    await loadChannels();
  }));
  body.querySelectorAll('button[data-block]').forEach((button) => button.addEventListener('click', async () => {
    await requestJson(`/api/channels/${Number(button.dataset.block)}`, { method: 'PATCH', body: JSON.stringify({ blocked: true, allowed: false }) });
    await loadChannels();
  }));
  body.querySelectorAll('button[data-disable]').forEach((button) => button.addEventListener('click', async () => {
    const id = Number(button.dataset.disable);
    const channel = allChannels.find((item) => item.id === id);
    await requestJson(`/api/channels/${id}`, { method: 'PATCH', body: JSON.stringify({ enabled: !channel.enabled }) });
    await loadChannels();
  }));
  body.querySelectorAll('button[data-delete]').forEach((button) => button.addEventListener('click', async () => {
    await requestJson(`/api/channels/${Number(button.dataset.delete)}`, { method: 'DELETE' });
    await loadChannels();
  }));
}

function renderLookupPreview(payload) {
  if (!payload?.found || !payload.channel) { preview.hidden = false; preview.innerHTML = `<h2>Nothing found</h2><p class="small">${escapeHtml(payload?.error || 'Try a different handle, channel ID, or channel URL.')}</p>`; latestLookup = null; return; }
  const channel = payload.channel;
  const videos = (payload.sample_videos || []).map((video) => `<a class="sample-video" href="/watch/${video.youtube_id}" target="_blank" rel="noopener noreferrer"><img src="${video.thumbnail_url}" alt="${escapeHtml(video.title)}" /><span>${escapeHtml(video.title)}</span></a>`).join('');
  preview.hidden = false;
  preview.innerHTML = `<div class="channel-preview-head">${channel.avatar_url ? `<img class="avatar preview-avatar" src="${channel.avatar_url}" alt="" />` : ''}<div><h2>${escapeHtml(channel.title || 'Untitled channel')}</h2><p class="small">${escapeHtml(channel.handle || '')} · ${escapeHtml(channel.youtube_id)}</p></div></div><p class="small clamp-text">${escapeHtml(channel.description || 'No description available.')}</p><p class="small">Subscribers: ${channel.subscriber_count ?? '—'} · Videos: ${channel.video_count ?? '—'}</p><h3>Recent samples</h3><div class="sample-grid">${videos || '<p class="small">No sample videos returned.</p>'}</div><div class="preview-actions"><button class="btn-primary" id="add-channel-btn">Add Channel</button><button class="btn-soft" id="block-channel-btn">Block Channel</button></div>`;
  latestLookup = payload;
  document.getElementById('add-channel-btn')?.addEventListener('click', () => submitFromPreview(false));
  document.getElementById('block-channel-btn')?.addEventListener('click', () => submitFromPreview(true));
}

async function submitFromPreview(blocked) {
  const categoryId = Number(String(new FormData(form).get('category') || '').trim()) || null;
  const created = await requestJson('/api/channels', { method: 'POST', body: JSON.stringify({ input: latestLookup.query, category_id: categoryId }) });
  if (blocked) await requestJson(`/api/channels/${created.id}`, { method: 'PATCH', body: JSON.stringify({ blocked: true, allowed: false, blocked_reason: 'Blocked by admin review' }) });
  await loadChannels();
}

async function loadChannels() { allChannels = await requestJson('/api/channels'); renderChannels(); }
async function loadCategories() { categories = await requestJson('/api/categories?include_disabled=true'); renderCategories(); renderChannels(); }

filters?.querySelectorAll('button[data-filter]').forEach((button) => button.addEventListener('click', () => {
  activeFilter = button.dataset.filter;
  filters.querySelectorAll('button[data-filter]').forEach((item) => item.classList.remove('active'));
  button.classList.add('active');
  renderChannels();
}));

document.getElementById('toggle-add-category')?.addEventListener('click', () => {
  createCategoryForm.hidden = !createCategoryForm.hidden;
});

createCategoryForm?.addEventListener('submit', async (event) => {
  event.preventDefault();
  const data = new FormData(createCategoryForm);
  await requestJson('/api/categories', { method: 'POST', body: JSON.stringify({ name: String(data.get('name') || '').trim(), daily_limit_minutes: Number(String(data.get('daily_limit_minutes') || '').trim()) || null }) });
  createCategoryForm.reset();
  createCategoryForm.hidden = true;
  showToast('Category created.');
  await loadCategories();
});

form.addEventListener('submit', async (event) => {
  event.preventDefault();
  const query = String(new FormData(form).get('query') || '').trim();
  if (!query) return;
  const response = await requestJson(`/api/channel-lookup?query=${encodeURIComponent(query)}`);
  renderLookupPreview(response);
});

Promise.all([loadChannels(), loadCategories()]).catch((error) => showToast(`Unable to load channels: ${error.message}`, 'error'));
