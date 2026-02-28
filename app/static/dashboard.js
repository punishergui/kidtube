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
  categoryId: null,
  kidId: null,
  channelFilter: queryParams.get('channel_id') || null,
  offset: 0,
  limit: 30,
  hasMore: true,
  searchResults: [],
};

function setFeedVisible(visible) {
  categoryPanel.hidden = !visible;
  newAdventures.hidden = !visible;
  latestVideos.hidden = !visible;
}

function formatDuration(seconds) {
  if (!Number.isFinite(seconds) || seconds <= 0) return '—';
  const s = Math.floor(seconds);
  const hrs = Math.floor(s / 3600);
  const mins = Math.floor((s % 3600) / 60);
  const secs = s % 60;
  if (hrs > 0) return `${hrs}:${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
  return `${mins}:${String(secs).padStart(2, '0')}`;
}

function categoryMatches(item) {
  if (state.categoryId !== null && Number(item.channel_category_id) !== Number(state.categoryId)) return false;
  if (state.channelFilter && String(item.channel_id) !== String(state.channelFilter)) return false;
  return true;
}

function renderCategories() {
  categoryPills.innerHTML = state.categories
    .map((category) => `<button class="pill ${Number(category.id) === Number(state.categoryId) || (category.id === null && state.categoryId === null) ? 'active' : ''}" data-category-id="${category.id ?? ''}">${category.name[0].toUpperCase()}${category.name.slice(1)}</button>`)
    .join('');
  categoryPills.querySelectorAll('button[data-category-id]').forEach((button) =>
    button.addEventListener('click', () => {
      const value = button.dataset.categoryId;
      state.categoryId = value === '' ? null : Number(value);
      renderCategories();
      renderVideos();
    }),
  );
}

function card(item) {
  return `<a class="video-card" href="/watch/${item.video_youtube_id}">
    <img class="thumb" src="${item.video_thumbnail_url}" alt="${item.video_title}" />
    <div class="card-body">
      <h3 class="video-title">${item.video_title}</h3>
      <p class="video-meta">${item.channel_title || 'Unknown'} · ${formatDuration(item.video_duration_seconds)}</p>
    </div>
  </a>`;
}

function shortCard(item) {
  return `<a class="shorts-card" href="/watch/${item.video_youtube_id}">
    <img class="thumb" src="${item.video_thumbnail_url}" alt="${item.video_title}" />
    <div class="card-body">
      <h3 class="video-title">${item.video_title}</h3>
      <p class="video-meta">${item.channel_title || 'Unknown'} · ${formatDuration(item.video_duration_seconds)}</p>
    </div>
  </a>`;
}

function renderVideos() {
  const visible = state.items.filter(categoryMatches);
  const latestVisible = state.latestPerChannel.filter(categoryMatches);
  grid.innerHTML = visible.length ? visible.map((item) => card(item)).join('') : '<article class="panel empty-state">No videos yet.</article>';
  latestGrid.innerHTML = latestVisible.length ? latestVisible.map((item) => card(item)).join('') : '<article class="panel empty-state">No latest videos yet.</article>';
  allowedChannelGrid.innerHTML = state.allowedChannels.length
    ? state.allowedChannels.map((channel) => `<a class="channel-pill" href="/channel/${channel.youtube_id}">${channel.avatar_url ? `<img class="channel-pill-avatar" src="${channel.avatar_url}" alt="${channel.title || channel.youtube_id}" />` : '<span class="channel-pill-avatar">📺</span>'}<span class="channel-pill-name">${channel.title || channel.youtube_id}</span></a>`).join('')
    : '<article class="panel empty-state">No allowed channels.</article>';
  shortsGrid.innerHTML = state.shorts.length ? state.shorts.map((item) => shortCard(item)).join('') : '<article class="panel empty-state">No shorts right now.</article>';
}

function startRequestCooldown(button, seconds) {
  const original = button.dataset.cooldownLabel || button.textContent || 'Request';
  button.dataset.cooldownLabel = original;
  let remaining = Number(seconds || 0);
  button.disabled = true;
  button.textContent = `Try again in ${remaining}s…`;
  const timer = window.setInterval(() => {
    remaining -= 1;
    if (remaining <= 0) {
      window.clearInterval(timer);
      button.disabled = false;
      button.textContent = original;
      return;
    }
    button.textContent = `Try again in ${remaining}s…`;
  }, 1000);
}

function renderSearchResults() {
  searchResultsWrap.hidden = !state.searchResults.length;
  if (!state.searchResults.length) return;
  const actionMarkup = (item) => {
    if (item.access_status === 'allowed') return `<a class="btn-secondary" href="/watch/${item.video_id}">Play</a>`;
    if (item.access_status === 'pending') return '<button class="btn-secondary" type="button" disabled>Pending</button>';
    return `<button class="btn-primary" data-request-video="${item.video_id}" data-request-channel="${item.channel_id || ''}">Request</button>`;
  };
  searchResultsGrid.innerHTML = state.searchResults.map((item) => `
    <article class="video-card">
      <img class="thumb" src="${item.thumbnail_url}" alt="${item.title}" />
      <div class="card-body"><h3 class="video-title">${item.title}</h3><p class="video-meta">${item.channel_title}</p>
      ${actionMarkup(item)}</div>
    </article>`).join('');
  searchResultsGrid.querySelectorAll('[data-request-video]').forEach((button) => button.addEventListener('click', async () => {
    if (!state.kidId) return;
    const channelId = button.dataset.requestChannel;
    const channelAllowed = state.allowedChannels.some((channel) => channel.youtube_id === channelId);
    const endpoint = channelId && !channelAllowed ? '/api/requests/channel-allow' : '/api/requests/video-allow';
    const youtubeId = channelId && !channelAllowed ? channelId : button.dataset.requestVideo;
    const response = await fetch(endpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ youtube_id: youtubeId, kid_id: state.kidId }),
    });

    let payload = null;
    try {
      payload = await response.json();
    } catch {
      payload = null;
    }

    if (response.status === 429) {
      const retryAfter = Number(payload?.retry_after || response.headers.get('Retry-After') || 30);
      startRequestCooldown(button, retryAfter);
      showToast(`Try again in ${retryAfter}s…`, 'error');
      return;
    }

    if (!response.ok) {
      showToast(`Request failed: ${payload?.detail || response.statusText}`, 'error');
      return;
    }

    showToast('Request sent');
  }));
}

function setupRowArrows() {
  document.querySelectorAll('.section-row, .channel-carousel').forEach((row) => {
    const parent = row.parentElement;
    if (!parent || parent.querySelector('.row-nav')) return;
    const controls = document.createElement('div');
    controls.className = 'row-nav';
    controls.innerHTML = '<button class="row-nav-btn" type="button" aria-label="Scroll left">◀</button><button class="row-nav-btn" type="button" aria-label="Scroll right">▶</button>';
    const [left, right] = controls.querySelectorAll('button');
    left.addEventListener('click', () => row.scrollBy({ left: -640, behavior: 'smooth' }));
    right.addEventListener('click', () => row.scrollBy({ left: 640, behavior: 'smooth' }));
    parent.appendChild(controls);
  });
}

async function loadMore() {
  if (!state.hasMore) return;
  const params = new URLSearchParams({ limit: String(state.limit), offset: String(state.offset) });
  if (state.channelFilter) params.set('channel_id', state.channelFilter);
  if (state.kidId) params.set('kid_id', String(state.kidId));
  const page = await requestJson(`/api/feed?${params.toString()}`);
  state.items.push(...page);
  state.offset += page.length;
  state.hasMore = page.length === state.limit;
  if (moreButton) moreButton.hidden = !state.hasMore;
  renderVideos();
}

async function loadFeedData() {
  if (!state.kidId) {
    setFeedVisible(false);
    return;
  }
  setFeedVisible(true);
  state.items = [];
  state.offset = 0;
  state.hasMore = true;
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
  setupRowArrows();
}

moreButton?.addEventListener('click', async () => {
  moreButton.disabled = true;
  await loadMore();
  moreButton.disabled = false;
});
window.addEventListener('kidtube:search-results', (event) => {
  state.searchResults = event.detail.results || [];
  renderSearchResults();
});


document.getElementById('switch-profile')?.addEventListener('click', async () => {
  await fetch('/api/session/logout', { method: 'POST' });
  window.location = '/';
});

document.getElementById('parent-controls')?.addEventListener('click', async () => {
  await fetch('/api/session/logout', { method: 'POST' });
  window.location = '/?admin=1';
});

loadDashboard().catch((error) => showToast(`Unable to load dashboard: ${error.message}`, 'error'));
