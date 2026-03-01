import { requestJson, showToast } from '/static/app.js';

const grid = document.getElementById('channel-video-grid');
const channelHeader = document.getElementById('channel-header');
const channelId = grid?.dataset.channelId;
const sentinel = document.getElementById('channel-feed-sentinel');
const spinner = sentinel?.querySelector('.feed-spinner');

const state = { observer: null, kidId: null, limit: 24, offset: 0, hasMore: true, loading: false };
const thumbIntervals = new WeakMap();

function escapeHtml(value) {
  return String(value || '').replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;').replaceAll('"', '&quot;').replaceAll("'", '&#39;');
}

function formatDuration(seconds) {
  if (!Number.isFinite(seconds) || seconds <= 0) return '—';
  const s = Math.floor(seconds); const hrs = Math.floor(s / 3600); const mins = Math.floor((s % 3600) / 60); const secs = s % 60;
  if (hrs > 0) return `${hrs}:${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
  return `${mins}:${String(secs).padStart(2, '0')}`;
}

function categoryClass(name) {
  const n = String(name || '').toLowerCase();
  if (n.includes('education')) return 'cat-education';
  if (n.includes('art')) return 'cat-art';
  return 'cat-fun';
}

function thumbsFor(videoId, current) {
  if (!videoId) return current ? [current] : [];
  return [current || `https://img.youtube.com/vi/${videoId}/hqdefault.jpg`, `https://img.youtube.com/vi/${videoId}/mqdefault.jpg`, `https://img.youtube.com/vi/${videoId}/hqdefault.jpg`, `https://img.youtube.com/vi/${videoId}/maxresdefault.jpg`];
}

function card(item) {
  const duration = formatDuration(item.video_duration_seconds);
  const category = channelHeader.dataset.category || 'Fun';
  const thumbs = thumbsFor(item.video_youtube_id, item.video_thumbnail_url).join(',');
  return `<a class="video-card panel channel-video-card" data-thumbs="${thumbs}" href="/watch/${item.video_youtube_id}">
    <div class="thumb-wrap ratio-16-9">
      <img class="thumb" src="${item.video_thumbnail_url}" alt="${escapeHtml(item.video_title)}" />
      <span class="category-badge ${categoryClass(category)}">${escapeHtml(category)}</span>
      <span class="duration-badge">${duration}</span>
    </div>
    <div class="card-body compact">
      <div class="channel-line">${channelHeader.dataset.avatar ? `<img class="mini-channel-avatar" src="${channelHeader.dataset.avatar}" alt="${escapeHtml(channelHeader.dataset.channelTitle || 'Channel')}" />` : '<span class="mini-channel-avatar">📺</span>'}<span>${escapeHtml(channelHeader.dataset.channelTitle || 'Unknown')}</span></div>
      <h3 class="video-title">${escapeHtml(item.video_title)}</h3>
      <p class="video-meta">${duration}</p>
    </div>
  </a>`;
}

function attachThumbCycle(root) {
  root.querySelectorAll('[data-thumbs]').forEach((el) => {
    const img = el.querySelector('img.thumb');
    if (!img) return;
    const thumbs = String(el.dataset.thumbs || '').split(',').filter(Boolean);
    if (!thumbs.length) return;
    const original = img.src;
    el.addEventListener('mouseenter', () => {
      if (thumbIntervals.has(el)) return;
      let idx = 0;
      const timer = window.setInterval(() => { idx = (idx + 1) % thumbs.length; img.src = thumbs[idx]; }, 800);
      thumbIntervals.set(el, timer);
    });
    el.addEventListener('mouseleave', () => {
      const timer = thumbIntervals.get(el);
      if (timer) { window.clearInterval(timer); thumbIntervals.delete(el); }
      img.src = original;
    });
  });
}

function updateSentinelUi() {
  if (!sentinel) return;
  sentinel.hidden = !state.hasMore;
  if (spinner) spinner.hidden = !state.loading;
}

async function loadMore() {
  if (!state.hasMore || state.loading) return;
  state.loading = true; updateSentinelUi();
  try {
    const params = new URLSearchParams({ limit: String(state.limit), offset: String(state.offset) });
    const rows = await requestJson(`/api/channels/${encodeURIComponent(channelId)}/videos?${params.toString()}`);
    if (rows.length) grid.insertAdjacentHTML('beforeend', rows.map(card).join(''));
    attachThumbCycle(grid);
    state.offset += rows.length;
    state.hasMore = rows.length === state.limit;
    if (!state.hasMore && state.observer) state.observer.disconnect();
  } finally {
    state.loading = false; updateSentinelUi();
  }
}

function setupInfiniteScroll() {
  if (!sentinel) return;
  state.observer = new IntersectionObserver((entries) => {
    entries.forEach((entry) => { if (entry.isIntersecting) void loadMore(); });
  }, { threshold: 0.1 });
  state.observer.observe(sentinel);
}

function sentinelVisible() {
  if (!sentinel) return false;
  const rect = sentinel.getBoundingClientRect();
  return rect.top < window.innerHeight && rect.bottom >= 0;
}

async function load() {
  try {
    const sessionState = await requestJson('/api/session');
    state.kidId = sessionState.kid_id;
    const channel = await requestJson(`/api/channels/youtube/${encodeURIComponent(channelId)}`);

    channelHeader.dataset.channelTitle = channel.title || channel.youtube_id || 'Unknown';
    channelHeader.dataset.avatar = channel.avatar_url || '';
    channelHeader.dataset.category = channel.category || 'Fun';
    channelHeader.innerHTML = `<div class="channel-page-meta">${channel.avatar_url ? `<img class="channel-page-avatar" src="${channel.avatar_url}" alt="${escapeHtml(channel.title || channel.youtube_id)}" />` : '<span class="channel-page-avatar">📺</span>'}<div><h2>${escapeHtml(channel.title || channel.youtube_id)}</h2><p class="small">${escapeHtml(channel.input || '')}</p></div></div>`;

    grid.innerHTML = '';
    setupInfiniteScroll();
    await loadMore();
    if (state.hasMore && sentinelVisible()) {
      await loadMore();
    }
    if (!grid.children.length) {
      grid.innerHTML = '<article class="empty-state panel">No videos yet.</article>';
      state.hasMore = false; updateSentinelUi();
    }
  } catch (error) {
    showToast(`Unable to load channel: ${error.message}`, 'error');
  }
}

load();
