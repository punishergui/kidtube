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
  categorySelect.innerHTML = '<option value="">Category (optional)</option>' + categories.filter((c) => c.enabled).map((category) => `<option value="${category.name}">${category.name}</option>`).join('');
  categoriesBody.innerHTML = categories.map((category) => `
    <article class="admin-card panel">
      <div class="admin-card-head"><h3>${escapeHtml(category.name)}</h3><span class="small">${category.enabled ? 'Enabled' : 'Disabled'}</span></div>
      <p class="small">Default limit: ${category.daily_limit_minutes ?? 'none'} minutes/day</p>
      <div class="preview-actions">
        <button class="btn-soft" data-toggle-category="${category.id}">${category.enabled ? 'Disable' : 'Enable'}</button>
        <button class="btn-secondary" data-delete-category="${category.id}">Disable (soft delete)</button>
      </div>
    </article>
  `).join('') || '<article class="empty-state">No categories yet.</article>';

  categoriesBody.querySelectorAll('button[data-toggle-category]').forEach((button) => button.addEventListener('click', async () => {
    const id = Number(button.dataset.toggleCategory);
    const category = categories.find((item) => item.id === id);
    await requestJson(`/api/categories/${id}`, { method: 'PATCH', body: JSON.stringify({ enabled: !category.enabled }) });
    await loadCategories();
  }));

  categoriesBody.querySelectorAll('button[data-delete-category]').forEach((button) => button.addEventListener('click', async () => {
    try { await requestJson(`/api/categories/${Number(button.dataset.deleteCategory)}?hard_delete=true`, { method: 'DELETE' }); } catch (error) { if (String(error.message).includes('archive')) { await requestJson(`/api/categories/${Number(button.dataset.deleteCategory)}?archive=true`, { method: 'DELETE' }); showToast('Category archived (in use).'); } else { throw error; } }
    await loadCategories();
  }));
}

function row(channel) {
  return `<article class="panel admin-card"><div class="admin-card-head"><h3>${channel.title || 'Untitled channel'}</h3><span class="small">${channel.youtube_id}</span></div><p class="small">Input: ${channel.input || '—'}</p><p class="small">Resolve: ${channel.resolve_status}${channel.resolve_error ? ` · ${channel.resolve_error}` : ''}</p><div class="switch-row"><label class="switch-field"><span>Allowed</span><input type="checkbox" data-id="${channel.id}" data-action="allowed" ${channel.allowed ? 'checked' : ''} /><span class="slider"></span></label><label class="switch-field"><span>Enabled</span><input type="checkbox" data-id="${channel.id}" data-action="enabled" ${channel.enabled ? 'checked' : ''} /><span class="slider"></span></label><label class="switch-field"><span>Blocked</span><input type="checkbox" data-id="${channel.id}" data-action="blocked" ${channel.blocked ? 'checked' : ''} /><span class="slider"></span></label></div><div class="reason-row"><input data-reason="${channel.id}" value="${channel.blocked_reason || ''}" placeholder="Blocked reason" /><button class="btn-soft" data-save-reason="${channel.id}">Save reason</button><button class="btn-secondary" data-delete="${channel.id}">Delete</button></div><p class="small">Last sync: ${formatDate(channel.last_sync)}</p></article>`;
}

function renderChannels() {
  const channels = allChannels.filter(matchesFilter);
  body.innerHTML = channels.length ? channels.map(row).join('') : '<article class="panel empty-state">No channels for this filter.</article>';
  body.querySelectorAll('input[data-action]').forEach((input) => input.addEventListener('change', async () => {
    const id = Number(input.dataset.id);
    const action = input.dataset.action;
    const channel = allChannels.find((item) => item.id === id);
    let payload;
    if (action === 'allowed') payload = { allowed: !channel.allowed };
    if (action === 'enabled') payload = { enabled: !channel.enabled };
    if (action === 'blocked') payload = { blocked: !channel.blocked, blocked_reason: body.querySelector(`input[data-reason="${id}"]`)?.value?.trim() || null };
    await requestJson(`/api/channels/${id}`, { method: 'PATCH', body: JSON.stringify(payload) });
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
  const category = String(new FormData(form).get('category') || '').trim() || null;
  const created = await requestJson('/api/channels', { method: 'POST', body: JSON.stringify({ input: latestLookup.query, category }) });
  if (blocked) await requestJson(`/api/channels/${created.id}`, { method: 'PATCH', body: JSON.stringify({ blocked: true, allowed: false, blocked_reason: 'Blocked by admin review' }) });
  await loadChannels();
}

async function loadChannels() { allChannels = await requestJson('/api/channels'); renderChannels(); }
async function loadCategories() { categories = await requestJson('/api/categories?include_disabled=true'); renderCategories(); }

filters?.querySelectorAll('button[data-filter]').forEach((button) => button.addEventListener('click', () => {
  activeFilter = button.dataset.filter;
  filters.querySelectorAll('button[data-filter]').forEach((item) => item.classList.remove('active'));
  button.classList.add('active');
  renderChannels();
}));

createCategoryForm?.addEventListener('submit', async (event) => {
  event.preventDefault();
  const data = new FormData(createCategoryForm);
  await requestJson('/api/categories', { method: 'POST', body: JSON.stringify({ name: String(data.get('name') || '').trim(), daily_limit_minutes: Number(String(data.get('daily_limit_minutes') || '').trim()) || null }) });
  createCategoryForm.reset();
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
