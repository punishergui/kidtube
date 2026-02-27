import { formatDate, requestJson, showToast } from '/static/app.js';

const grid = document.getElementById('dashboard-grid');

function card(item) {
  return `
    <a class="video-card panel" href="/watch/${item.video_youtube_id}">
      <img class="thumb" src="${item.video_thumbnail_url}" alt="${item.video_title}" loading="lazy" />
      <div class="video-card-body">
        <div class="channel-row">
          <img class="avatar" src="${item.channel_avatar_url || ''}" alt="" />
          <span>${item.channel_title || 'Unknown channel'}</span>
        </div>
        <h3 class="video-title">${item.video_title}</h3>
        <p class="small">${formatDate(item.video_published_at)}</p>
      </div>
    </a>
  `;
}

async function loadDashboard() {
  try {
    const items = await requestJson('/api/feed/latest-per-channel');
    if (!items.length) {
      grid.innerHTML = '<article class="panel" style="padding:1rem;">No videos yet. Run sync to populate the feed.</article>';
      return;
    }
    grid.innerHTML = items.map(card).join('');
  } catch (error) {
    showToast(`Unable to load feed: ${error.message}`, 'error');
  }
}

loadDashboard();
