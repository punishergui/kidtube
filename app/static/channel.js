import { requestJson, showToast } from '/static/app.js';

const grid = document.getElementById('channel-video-grid');
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

function formatDuration(seconds) {
  if (!Number.isFinite(seconds) || seconds <= 0) return '—';
  const s = Math.floor(seconds);
  const hrs = Math.floor(s / 3600);
  const mins = Math.floor((s % 3600) / 60);
  const secs = s % 60;
  if (hrs > 0) return `${hrs}:${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
  return `${mins}:${String(secs).padStart(2, '0')}`;
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
        <div>
          <h2>${escapeHtml(channel.title || channel.youtube_id)}</h2>
          <p class="small">${escapeHtml(channel.input || '')}</p>
        </div>
      </div>
    `;

    grid.innerHTML = rows.length
      ? rows.map((item) => `<a class="video-card panel" href="/watch/${item.video_youtube_id}"><img class="thumb" src="${item.video_thumbnail_url}" alt="${escapeHtml(item.video_title)}" /><div class="card-body"><h3>${escapeHtml(item.video_title)}</h3><p class="video-meta">${formatDuration(item.video_duration_seconds)}</p></div></a>`).join('')
      : '<article class="empty-state panel">No videos yet.</article>';
  } catch (error) {
    showToast(`Unable to load channel: ${error.message}`, 'error');
  }
}

load();
