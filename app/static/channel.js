import { requestJson, showToast } from '/static/app.js';

const grid = document.getElementById('channel-video-grid');
const latestRow = document.getElementById('channel-latest-row');
const channelHeader = document.getElementById('channel-header');
const channelId = grid?.dataset.channelId;

function escapeHtml(value) {
  return String(value || '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}

function card(item) {
  return `<a class="video-card" href="/watch/${item.video_youtube_id}">
    <img class="thumb" src="${item.video_thumbnail_url}" alt="${escapeHtml(item.video_title)}" />
    <div class="card-body"><h3 class="video-title">${escapeHtml(item.video_title)}</h3></div>
  </a>`;
}

async function load() {
  try {
    const sessionState = await requestJson('/api/session');
    const kidId = sessionState.kid_id;
    const [channel, rows] = await Promise.all([
      requestJson(`/api/channels/youtube/${encodeURIComponent(channelId)}?kid_id=${kidId || ''}`),
      requestJson(`/api/channels/${encodeURIComponent(channelId)}/videos?kid_id=${kidId || ''}`),
    ]);

    channelHeader.innerHTML = `
      <div class="channel-page-meta">
        ${channel.avatar_url ? `<img class="channel-page-avatar" src="${channel.avatar_url}" alt="${escapeHtml(channel.title || channel.youtube_id)}" />` : '<span class="channel-page-avatar">📺</span>'}
        <div class="channel-hero-title-wrap">
          <h2>${escapeHtml(channel.title || channel.youtube_id)}</h2>
          <span class="channel-badge">Subscribed-safe</span>
          <p class="small">${escapeHtml(channel.input || '')}</p>
        </div>
      </div>
    `;

    latestRow.innerHTML = rows.length
      ? rows.slice(0, 8).map((item) => card(item)).join('')
      : '<article class="empty-state panel">No videos yet.</article>';

    grid.innerHTML = rows.length
      ? rows.map((item) => card(item)).join('')
      : '<article class="empty-state panel">No videos yet.</article>';
  } catch (error) {
    showToast(`Unable to load channel: ${error.message}`, 'error');
  }
}

load();
