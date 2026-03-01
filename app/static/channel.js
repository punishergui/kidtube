import { requestJson, showToast } from '/static/app.js';

const grid = document.getElementById('channel-video-grid');
const channelHeader = document.getElementById('channel-header');
const channelId = grid?.dataset.channelId;
const sentinel = document.getElementById('channel-feed-sentinel');
const spinner = sentinel?.querySelector('.feed-spinner');

const state = {
  kidId: null,
  limit: 24,
  offset: 0,
  hasMore: true,
  loading: false,
};

function escapeHtml(value) {
  return String(value || '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
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

function card(item) {
  return `<a class="video-card panel channel-video-card" href="/watch/${item.video_youtube_id}">
    <div class="thumb-wrap"><img class="thumb" src="${item.video_thumbnail_url}" alt="${escapeHtml(item.video_title)}" /></div>
    <div class="card-body">
      <h3 class="video-title">${escapeHtml(item.video_title)}</h3>
      <p class="video-meta">${escapeHtml(channelHeader.dataset.channelTitle || 'Unknown')} · ${formatDuration(item.video_duration_seconds)}</p>
    </div>
  </a>`;
}

function updateSentinelUi() {
  if (!sentinel) return;
  sentinel.hidden = !state.hasMore;
  if (spinner) spinner.hidden = !state.loading;
}

async function loadMore() {
  if (!state.hasMore || state.loading) return;
  state.loading = true;
  updateSentinelUi();
  try {
    const params = new URLSearchParams({ limit: String(state.limit), offset: String(state.offset) });
    if (state.kidId) params.set('kid_id', String(state.kidId));
    const rows = await requestJson(`/api/channels/${encodeURIComponent(channelId)}/videos?${params.toString()}`);
    if (rows.length) {
      grid.insertAdjacentHTML('beforeend', rows.map(card).join(''));
    }
    state.offset += rows.length;
    state.hasMore = rows.length === state.limit;
  } finally {
    state.loading = false;
    updateSentinelUi();
  }
}

function setupInfiniteScroll() {
  if (!sentinel) return;
  const observer = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (entry.isIntersecting) {
        void loadMore();
      }
    });
  }, { threshold: 0.1 });
  observer.observe(sentinel);
}

async function load() {
  try {
    const sessionState = await requestJson('/api/session');
    state.kidId = sessionState.kid_id;
    const channel = await requestJson(`/api/channels/youtube/${encodeURIComponent(channelId)}?kid_id=${state.kidId || ''}`);

    channelHeader.dataset.channelTitle = channel.title || channel.youtube_id || 'Unknown';
    channelHeader.innerHTML = `
      <div class="channel-page-meta">
        ${channel.avatar_url ? `<img class="channel-page-avatar" src="${channel.avatar_url}" alt="${escapeHtml(channel.title || channel.youtube_id)}" />` : '<span class="channel-page-avatar">📺</span>'}
        <div>
          <h2>${escapeHtml(channel.title || channel.youtube_id)}</h2>
          <p class="small">${escapeHtml(channel.input || '')}</p>
        </div>
      </div>
    `;

    grid.innerHTML = '';
    setupInfiniteScroll();
    await loadMore();
    if (!grid.children.length) {
      grid.innerHTML = '<article class="empty-state panel">No videos yet.</article>';
      state.hasMore = false;
      updateSentinelUi();
    }
  } catch (error) {
    showToast(`Unable to load channel: ${error.message}`, 'error');
  }
}

load();
