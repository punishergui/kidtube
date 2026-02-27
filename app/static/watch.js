import { formatDate, requestJson, showToast } from '/static/app.js';

const container = document.getElementById('watch-container');
const youtubeId = container?.dataset.youtubeId;

function renderNotFound() {
  container.innerHTML = `
    <article class="panel" style="padding:1rem;">
      <h2>Video not found</h2>
      <p class="small">This video is not available in KidTube yet. Try running a sync and come back.</p>
    </article>
  `;
}

async function loadVideo() {
  if (!youtubeId) {
    renderNotFound();
    return;
  }

  try {
    const video = await requestJson(`/api/videos/${youtubeId}`);
    container.innerHTML = `
      <section class="player-wrap panel">
        <iframe
          src="https://www.youtube-nocookie.com/embed/${video.youtube_id}"
          title="${video.title}"
          allow="autoplay; encrypted-media; picture-in-picture"
          sandbox="allow-scripts allow-same-origin allow-presentation"
          referrerpolicy="no-referrer"
          allowfullscreen
        ></iframe>
      </section>
      <article class="panel" style="padding:1rem;">
        <h2>${video.title}</h2>
        <div class="channel-row">
          <img class="avatar" src="${video.channel_avatar_url || ''}" alt="" />
          <span>${video.channel_title || 'Unknown channel'}</span>
        </div>
        <p class="small">Published: ${formatDate(video.published_at)}</p>
      </article>
    `;
  } catch (error) {
    renderNotFound();
    if (!String(error.message).includes('404')) {
      showToast(`Unable to load video: ${error.message}`, 'error');
    }
  }
}

loadVideo();
