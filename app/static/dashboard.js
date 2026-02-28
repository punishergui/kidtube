import { requestJson, showToast } from '/static/app.js';

const grid = document.getElementById('dashboard-grid');
const latestGrid = document.getElementById('latest-channel-grid');
const categoryPills = document.getElementById('category-pills');
const moreButton = document.getElementById('see-more-btn');
const categoryPanel = document.getElementById('category-panel');
const newAdventures = document.getElementById('new-adventures');
const latestVideos = document.getElementById('latest-videos');
const searchResultsWrap = document.getElementById('search-results');
const searchResultsGrid = document.getElementById('search-results-grid');
const allowedChannelGrid = document.getElementById('allowed-channel-grid');
const shortsGrid = document.getElementById('shorts-grid');

const queryParams = new URLSearchParams(window.location.search);

const state = {
  items: [],
  latestPerChannel: [],
  allowedChannels: [],
  shorts: [],
  categories: [{ id: null, name: 'all', enabled: true }],
  category: 'all',
  kidId: null,
  channelFilter: queryParams.get('channel_id') || null,
  offset: 0,
  limit: 30,
  hasMore: true,
  searchResults: [],
};

function setFeedVisible(visible) { categoryPanel.hidden = !visible; newAdventures.hidden = !visible; latestVideos.hidden = !visible; }
function formatDuration(seconds) { if (!Number.isFinite(seconds) || seconds <= 0) return '5:00'; const mins = Math.floor(seconds / 60); const secs = seconds % 60; return `${mins}:${String(secs).padStart(2, '0')}`; }
function normalizeCategory(item) { return String(item.channel_category || item.category || '').toLowerCase(); }
function categoryMatches(item) { if (state.category !== 'all' && normalizeCategory(item) !== state.category) return false; if (state.channelFilter && String(item.channel_id) !== String(state.channelFilter)) return false; return true; }

function renderCategories() {
  categoryPills.innerHTML = state.categories.map((category) => `<button class="pill ${category.name === state.category ? 'active' : ''}" data-category="${category.name}">${category.name[0].toUpperCase()}${category.name.slice(1)}</button>`).join('');
  categoryPills.querySelectorAll('button[data-category]').forEach((button) => button.addEventListener('click', () => { state.category = button.dataset.category; renderCategories(); renderVideos(); }));
}
function card(item, isShort = false) { return `<a class="video-card panel ${isShort ? 'short-card' : ''}" href="/watch/${item.video_youtube_id}"><img class="thumb" src="${item.video_thumbnail_url}" alt="${item.video_title}" /><div><h3 class="video-title">${item.video_title}</h3><p class="small">${item.channel_title || 'Unknown'} · ${formatDuration(item.video_duration_seconds)}</p></div></a>`; }

function renderVideos() {
  const visible = state.items.filter(categoryMatches);
  grid.innerHTML = visible.length ? visible.map((item) => card(item)).join('') : '<article class="panel empty-state">No videos yet.</article>';
  latestGrid.innerHTML = state.latestPerChannel.length ? state.latestPerChannel.map((item) => card(item)).join('') : '<article class="panel empty-state">No latest videos yet.</article>';
  allowedChannelGrid.innerHTML = state.allowedChannels.length
    ? state.allowedChannels.map((channel) => `<a class="channel-chip panel" href="/channel/${channel.youtube_id}">${channel.avatar_url ? `<img class="channel-chip-avatar" src="${channel.avatar_url}" alt="${channel.title || channel.youtube_id}" />` : '<span class="channel-chip-avatar">📺</span>'}<span>${channel.title || channel.youtube_id}</span></a>`).join('')
    : '<article class="panel empty-state">No allowed channels.</article>';
  shortsGrid.innerHTML = state.shorts.length ? state.shorts.map((item) => card(item, true)).join('') : '<article class="panel empty-state">No shorts right now.</article>';
}

function renderSearchResults() {
  searchResultsWrap.hidden = !state.searchResults.length;
  if (!state.searchResults.length) return;
  searchResultsGrid.innerHTML = state.searchResults.map((item) => `
    <article class="panel video-card">
      <img class="thumb" src="${item.thumbnail_url}" alt="${item.title}" />
      <div><h3 class="video-title">${item.title}</h3><p class="small">${item.channel_title}</p>
      <button class="btn-primary" data-request-video="${item.video_id}" data-request-channel="${item.channel_id || ''}">Request</button></div>
    </article>`).join('');
  searchResultsGrid.querySelectorAll('[data-request-video]').forEach((button) => button.addEventListener('click', async () => {
    if (!state.kidId) return;
    const channelId = button.dataset.requestChannel;
    const channelAllowed = state.allowedChannels.some((channel) => channel.youtube_id === channelId);
    if (channelId && !channelAllowed) {
      await requestJson('/api/requests/channel-allow', { method: 'POST', body: JSON.stringify({ youtube_id: channelId, kid_id: state.kidId }) });
    } else {
      await requestJson('/api/requests/video-allow', { method: 'POST', body: JSON.stringify({ youtube_id: button.dataset.requestVideo, kid_id: state.kidId }) });
    }
    showToast('Request sent');
  }));
}

async function loadMore() { if (!state.hasMore) return; const params = new URLSearchParams({ limit: String(state.limit), offset: String(state.offset) }); if (state.channelFilter) params.set('channel_id', state.channelFilter); if (state.kidId) params.set('kid_id', String(state.kidId)); const page = await requestJson(`/api/feed?${params.toString()}`); state.items.push(...page); state.offset += page.length; state.hasMore = page.length === state.limit; if (moreButton) moreButton.hidden = !state.hasMore; renderVideos(); }

async function loadFeedData() {
  if (!state.kidId) { setFeedVisible(false); return; }
  setFeedVisible(true); state.items = []; state.offset = 0; state.hasMore = true;
  [state.latestPerChannel, state.allowedChannels, state.shorts] = await Promise.all([
    requestJson(`/api/feed/latest-per-channel?kid_id=${state.kidId}`),
    requestJson(`/api/channels/allowed?kid_id=${state.kidId}`),
    requestJson(`/api/feed/shorts?kid_id=${state.kidId}`),
  ]);
  await loadMore();
}

async function loadDashboard() {
  const [sessionState, apiCategories] = await Promise.all([requestJson('/api/session'), requestJson('/api/categories')]);
  state.categories = [{ id: null, name: 'all', enabled: true }, ...apiCategories.map((c) => ({ id: c.id, name: c.name, enabled: c.enabled }))];
  state.kidId = sessionState.kid_id;
  renderCategories();
  await loadFeedData();
}

moreButton?.addEventListener('click', async () => { moreButton.disabled = true; await loadMore(); moreButton.disabled = false; });
window.addEventListener('kidtube:search-results', (event) => { state.searchResults = event.detail.results || []; renderSearchResults(); });


document.getElementById('switch-profile')?.addEventListener('click', async () => {
  await fetch('/api/session/logout', { method: 'POST' });
  window.location = '/';
});

document.getElementById('parent-controls')?.addEventListener('click', async () => {
  await fetch('/api/session/logout', { method: 'POST' });
  window.location = '/?admin=1';
});

loadDashboard().catch((error) => showToast(`Unable to load dashboard: ${error.message}`, 'error'));
