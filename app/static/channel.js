import { requestJson, showToast } from '/static/app.js';

const grid = document.getElementById('channel-video-grid');
const channelId = grid?.dataset.channelId;

async function load() {
  try {
    const sessionState = await requestJson('/api/session');
    const kidId = sessionState.kid_id;
    const rows = await requestJson(`/api/channels/${encodeURIComponent(channelId)}/videos?kid_id=${kidId || ''}`);
    grid.innerHTML = rows.length ? rows.map((item) => `<a class="video-card panel" href="/watch/${item.video_youtube_id}"><img class="thumb" src="${item.video_thumbnail_url}" alt="${item.video_title}" /><h3>${item.video_title}</h3></a>`).join('') : '<article class="empty-state panel">No videos yet.</article>';
  } catch (error) {
    showToast(`Unable to load channel: ${error.message}`, 'error');
  }
}

load();
