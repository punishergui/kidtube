import { requestJson, showToast } from '/static/app.js';

const grid = document.getElementById('dashboard-grid');
const continueGrid = document.getElementById('continue-grid');
const latestGrid = document.getElementById('latest-channel-grid');
const categoryPills = document.getElementById('category-pills');
const categoryRows = document.getElementById('category-rows');
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

function setFeedVisible(visible) {
  categoryPanel.hidden = !visible;
  newAdventures.hidden = !visible;
  latestVideos.hidden = !visible;
}

function formatDuration(seconds) {
  if (!Number.isFinite(seconds) || seconds <= 0) return '5:00';
  const mins = Math.floor(seconds / 60);
  const secs = seconds % 60;
  return `${mins}:${String(secs).padStart(2, '0')}`;
}

function normalizeCategory(item) {
  return String(item.channel_category || item.category || '').toLowerCase();
}

function categoryMatches(item) {
  if (state.category !== 'all' && normalizeCategory(item) !== state.category) return false;
  if (state.channelFilter && String(item.channel_id) !== String(state.channelFilter)) return false;
  return true;
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
  return `<a class="shorts-card" href="/watch/${item.video_youtube_id}?mode=shorts">
    <img class="thumb" src="${item.video_thumbnail_url}" alt="${item.video_title}" />
    <div class="card-body">
      <h3 class="video-title">${item.video_title}</h3>
      <p class="video-meta">${item.channel_title || 'Unknown'} · ${formatDuration(item.video_duration_seconds)}</p>
    </div>
  </a>`;
}

function renderCategories() {
  categoryPills.innerHTML = state.categories
    .map(
      (category) =>
        `<button class="pill ${category.name === state.category ? 'active' : ''}" data-category="${category.name}">${category.name[0].toUpperCase()}${category.name.slice(1)}</button>`,
    )
    .join('');

  categoryPills.querySelectorAll('button[data-category]').forEach((button) =>
    button.addEventListener('click', () => {
      state.category = button.dataset.category;
      renderCategories();
      renderVideos();
    }),
  );
}

function renderCategoryRows() {
  const visibleItems = state.items.filter((item) => !state.channelFilter || String(item.channel_id) === String(state.channelFilter));
  const grouped = new Map();
  visibleItems.forEach((item) => {
    const key = normalizeCategory(item) || 'other';
    if (!grouped.has(key)) grouped.set(key, []);
    grouped.get(key).push(item);
  });

  const rows = [...grouped.entries()].filter(([key]) => key !== 'all').slice(0, 4);
  categoryRows.innerHTML = rows
    .map(
      ([name, items]) => `
      <section class="video-section">
        <div class="section-head"><h2>${name[0].toUpperCase()}${name.slice(1)}</h2></div>
        <section class="section-row">${items.slice(0, 12).map((item) => card(item)).join('')}</section>
      </section>`,
    )
    .join('');
}

function renderVideos() {
  const visible = state.items.filter(categoryMatches);
  grid.innerHTML = visible.length
    ? visible.map((item) => card(item)).join('')
    : '<article class="panel empty-state">No videos yet.</article>';

  continueGrid.innerHTML = visible.length
    ? visible.slice(0, 8).map((item) => card(item)).join('')
    : '<article class="panel empty-state">No recent videos yet.</article>';

  latestGrid.innerHTML = state.latestPerChannel.length
    ? state.latestPerChannel.map((item) => card(item)).join('')
    : '<article class="panel empty-state">No latest videos yet.</article>';

  allowedChannelGrid.innerHTML = state.allowedChannels.length
    ? state.allowedChannels
        .map(
          (channel) =>
            `<a class="channel-pill" href="/channel/${channel.youtube_id}">${channel.avatar_url ? `<img class="channel-pill-avatar" src="${channel.avatar_url}" alt="${channel.title || channel.youtube_id}" />` : '<span class="channel-pill-avatar">📺</span>'}<span class="channel-pill-name">${channel.title || channel.youtube_id}</span></a>`,
        )
        .join('')
    : '<article class="panel empty-state">No allowed channels.</article>';

  shortsGrid.innerHTML = state.shorts.length
    ? state.shorts.map((item) => shortCard(item)).join('')
    : '<article class="panel empty-state">No shorts right now.</article>';

  renderCategoryRows();
}

function renderSearchResults() {
  searchResultsWrap.hidden = !state.searchResults.length;
  if (!state.searchResults.length) return;

  const actionMarkup = (item) => {
    if (item.access_state === 'play') return `<a class="btn-secondary" href="/watch/${item.video_id}">Play</a>`;
    if (item.access_state === 'pending') return '<button class="btn-secondary" type="button" disabled>Pending</button>';
    if (item.access_state === 'denied') return '<button class="btn-secondary" type="button" disabled>Denied</button>';
    if (item.access_state === 'blocked') return '<button class="btn-secondary" type="button" disabled>Blocked</button>';
    return `<button class="btn-primary" data-request-video="${item.video_id}" data-request-channel="${item.channel_id || ''}">Request</button>`;
  };

  searchResultsGrid.innerHTML = state.searchResults
    .map(
      (item) => `
    <article class="video-card">
      <img class="thumb" src="${item.thumbnail_url}" alt="${item.title}" />
      <div class="card-body"><h3 class="video-title">${item.title}</h3><p class="video-meta">${item.channel_title}</p>
      ${actionMarkup(item)}</div>
    </article>`,
    )
    .join('');

  searchResultsGrid.querySelectorAll('[data-request-video]').forEach((button) =>
    button.addEventListener('click', async () => {
      if (!state.kidId) return;
      const channelId = button.dataset.requestChannel;
      const channelAllowed = state.allowedChannels.some((channel) => channel.youtube_id === channelId);
      if (channelId && !channelAllowed) {
        await requestJson('/api/requests/channel-allow', {
          method: 'POST',
          body: JSON.stringify({ youtube_id: channelId, kid_id: state.kidId }),
        });
      }
      await requestJson('/api/requests/video', {
        method: 'POST',
        body: JSON.stringify({ youtube_id: button.dataset.requestVideo, kid_id: state.kidId }),
      });
      showToast('Request sent for parent approval.', 'success');
      button.disabled = true;
      button.textContent = 'Pending';
      button.className = 'btn-secondary';
    }),
  );
}

async function loadKid() {
  const sessionState = await requestJson('/api/session');
  if (!sessionState.kid_id) {
    window.location.assign('/profiles');
    return;
  }
  state.kidId = sessionState.kid_id;
}

async function loadFeed(reset = false) {
  if (!state.kidId) return;
  if (reset) {
    state.offset = 0;
    state.items = [];
    state.hasMore = true;
  }
  if (!state.hasMore) return;

  const selectedCategory = state.category === 'all' ? '' : state.category;
  const params = new URLSearchParams({
    kid_id: String(state.kidId),
    limit: String(state.limit),
    offset: String(state.offset),
  });
  if (selectedCategory) params.set('category', selectedCategory);

  const rows = await requestJson(`/api/feed/videos?${params.toString()}`);
  if (!Array.isArray(rows)) return;
  state.items.push(...rows);
  state.offset += rows.length;
  state.hasMore = rows.length === state.limit;
  if (moreButton) moreButton.hidden = !state.hasMore;
}

async function loadData() {
  if (!state.kidId) return;
  const [categories, latest, allowedChannels, shorts] = await Promise.all([
    requestJson('/api/categories'),
    requestJson(`/api/feed/latest-per-channel?kid_id=${state.kidId}`),
    requestJson(`/api/channels?kid_id=${state.kidId}`),
    requestJson(`/api/feed/shorts?kid_id=${state.kidId}`),
  ]);

  state.categories = [{ id: null, name: 'all', enabled: true }, ...(categories || [])]
    .filter((category) => category && category.name)
    .map((category) => ({
      id: category.id ?? null,
      name: String(category.name).toLowerCase(),
      enabled: category.enabled !== false,
    }));

  if (!state.categories.some((item) => item.name === state.category)) {
    state.category = 'all';
  }

  state.latestPerChannel = Array.isArray(latest) ? latest : [];
  state.allowedChannels = Array.isArray(allowedChannels) ? allowedChannels.filter((channel) => channel.allowed !== false) : [];
  state.shorts = Array.isArray(shorts) ? shorts : [];
}

async function handleSearch(query) {
  const trimmed = query.trim();
  if (!trimmed) {
    state.searchResults = [];
    renderSearchResults();
    setFeedVisible(true);
    return;
  }

  setFeedVisible(false);
  state.searchResults = await requestJson(`/api/search/videos?q=${encodeURIComponent(trimmed)}&kid_id=${state.kidId}`);
  renderSearchResults();
}

function setupEvents() {
  moreButton?.addEventListener('click', async () => {
    await loadFeed(false);
    renderVideos();
  });

  const switchProfile = document.getElementById('switch-profile');
  const parentControls = document.getElementById('parent-controls');
  switchProfile?.addEventListener('click', () => window.location.assign('/profiles'));
  parentControls?.addEventListener('click', () => window.location.assign('/profiles?admin=1'));

  const searchInput = document.getElementById('header-search-input');
  const searchForm = document.getElementById('header-search-form');
  let searchTimer;

  const trigger = () => {
    window.clearTimeout(searchTimer);
    searchTimer = window.setTimeout(() => {
      void handleSearch(searchInput?.value || '');
    }, 220);
  };

  searchInput?.addEventListener('input', trigger);
  searchForm?.addEventListener('submit', (event) => {
    event.preventDefault();
    void handleSearch(searchInput?.value || '');
  });
}

async function init() {
  try {
    await loadKid();
    await Promise.all([loadData(), loadFeed(true)]);
    renderCategories();
    renderVideos();
    renderSearchResults();
    setupEvents();
  } catch (error) {
    showToast(`Unable to load dashboard: ${error.message}`, 'error');
  }
}

init();
