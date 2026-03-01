import { requestJson, showToast } from '/static/app.js';

const grid = document.getElementById('channel-video-grid');
const channelHeader = document.getElementById('channel-header');
const channelId = grid?.dataset.channelId;
const sentinel = document.getElementById('channel-feed-sentinel');
const spinner = sentinel?.querySelector('.feed-spinner');

const state = { observer: null, kidId: null, limit: 24, offset: 0, hasMore: true, loading: false, contentType: 'videos' };
let thumbPreviewInitialized = false;

function escapeHtml(value) {
  return String(value || '').replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;').replaceAll('"', '&quot;').replaceAll("'", '&#39;');
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

function formatViews(n) {
  if (!n || n <= 0) return '';
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1).replace(/\.0$/, '')}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1).replace(/\.0$/, '')}K`;
  return String(n);
}

function formatSubscribers(n) {
  if (!n) return '';
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1).replace(/\.0$/, '')}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1).replace(/\.0$/, '')}K`;
  return String(n);
}

function categoryClass(name) {
  const n = String(name || '').toLowerCase().trim();
  if (n.includes('edu') || n.includes('learn') || n.includes('school')) return 'cat-education';
  if (n.includes('art') || n.includes('draw') || n.includes('craft')) return 'cat-art';
  if (n.includes('kid') || n.includes('fun') || n.includes('play')) return 'cat-fun';
  return 'cat-fun';
}

function card(item) {
  const duration = formatDuration(item.video_duration_seconds);
  const categoryLabel = channelHeader.dataset.categoryName || channelHeader.dataset.category || 'Fun';
  const category = categoryLabel;
  return `<a class="video-card panel channel-video-card" data-video-id="${item.video_youtube_id}" href="/watch/${item.video_youtube_id}">
    <div class="thumbnail-wrap ratio-16-9">
      <img class="video-thumbnail" src="${item.video_thumbnail_url}" alt="${escapeHtml(item.video_title)}" />
      <span class="category-badge ${categoryClass(category)}">${escapeHtml(category)}</span>
      <span class="duration-badge">${duration}</span>
    </div>
    <div class="card-body compact">
      <h3 class="video-title">${escapeHtml(item.video_title)}</h3>
      <p class="video-meta">${escapeHtml(channelHeader.dataset.channelTitle || 'Unknown')}${item.video_view_count ? ` · ${formatViews(item.video_view_count)} views` : ''}</p>
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
    const params = new URLSearchParams({ limit: String(state.limit), offset: String(state.offset), content_type: state.contentType });
    const rows = await requestJson(`/api/channels/${encodeURIComponent(channelId)}/videos?${params.toString()}`);
    if (rows.length) grid.insertAdjacentHTML('beforeend', rows.map(card).join(''));
    if (!thumbPreviewInitialized && rows.length) {
      window.initThumbPreview?.({ containerId: 'channel-video-grid', cardSelector: '.video-card', thumbClass: 'video-thumbnail' });
      thumbPreviewInitialized = true;
    }
    state.offset += rows.length;
    state.hasMore = rows.length === state.limit;
    if (!state.hasMore && state.observer) state.observer.disconnect();
  } finally {
    state.loading = false;
    updateSentinelUi();
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
    channelHeader.dataset.categoryName = channel.category_name || '';
    const bannerStyle = channel.banner_url
      ? `style="background-image: url('${channel.banner_url}'); background-size: cover; background-position: center; min-height: 120px;"`
      : '';
    const subsText = channel.subscriber_count
      ? formatSubscribers(channel.subscriber_count)
      : '';
    channelHeader.innerHTML = `
      <div class="channel-banner" ${bannerStyle}>
        <div class="channel-banner-overlay">
          <div class="channel-page-meta">
            ${channel.avatar_url
              ? `<img class="channel-page-avatar" src="${channel.avatar_url}" alt="${escapeHtml(channel.title || channel.youtube_id)}" />`
              : '<span class="channel-page-avatar channel-page-avatar-placeholder">📺</span>'}
            <div class="channel-page-info">
              <h2 class="channel-page-title">${escapeHtml(channel.title || channel.youtube_id)}</h2>
              ${channel.input ? `<p class="channel-page-handle small">${escapeHtml(channel.input)}</p>` : ''}
              ${subsText ? `<p class="channel-page-subs small">${subsText} subscribers</p>` : ''}
              ${channel.description ? `<p class="channel-page-desc small">${escapeHtml(channel.description.slice(0, 200))}${channel.description.length > 200 ? '…' : ''}</p>` : ''}
            </div>
          </div>
        </div>
      </div>`;

    const heading = document.getElementById('channel-videos-heading');
    if (heading) heading.textContent = state.contentType === 'shorts' ? 'Channel Shorts' : 'Channel Videos';

    document.querySelectorAll('.channel-tab').forEach((tab) => {
      tab.classList.toggle('active', tab.dataset.contentType === state.contentType);
      tab.addEventListener('click', async () => {
        const nextType = tab.dataset.contentType || 'videos';
        if (nextType === state.contentType) return;
        state.contentType = nextType;
        state.offset = 0;
        state.hasMore = true;
        grid.innerHTML = '';
        document.querySelectorAll('.channel-tab').forEach((btn) => btn.classList.toggle('active', btn.dataset.contentType === state.contentType));
        if (heading) heading.textContent = state.contentType === 'shorts' ? 'Channel Shorts' : 'Channel Videos';
        if (state.observer && sentinel) state.observer.observe(sentinel);
        updateSentinelUi();
        await loadMore();
      });
    });

    grid.innerHTML = '';
    setupInfiniteScroll();
    updateSentinelUi();
    await loadMore();
    if (state.hasMore && sentinelVisible()) {
      await loadMore();
    }
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
