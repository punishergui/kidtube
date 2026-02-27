import { formatDate, requestJson, showToast } from '/static/app.js';

const container = document.getElementById('watch-container');
const youtubeId = container?.dataset.youtubeId;
const embedOrigin = container?.dataset.embedOrigin;
const readyTimeoutMs = 7000;

let fallbackTimer = null;
let playerReady = false;

function escapeHtml(value) {
  return String(value)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}

function getChannelFilterHref(channelId) {
  if (!channelId) return '/';
  return `/?channel=${encodeURIComponent(channelId)}`;
}

function showPlaybackFallback(channelId) {
  const fallback = document.getElementById('watch-fallback');
  if (!fallback) return;

  fallback.hidden = false;
  const filteredLink = fallback.querySelector('[data-channel-link]');
  if (filteredLink) {
    filteredLink.href = getChannelFilterHref(channelId);
  }
}

function markReady() {
  playerReady = true;
  const loading = document.getElementById('watch-loading');
  const fallback = document.getElementById('watch-fallback');
  if (loading) loading.hidden = true;
  if (fallback) fallback.hidden = true;
  if (fallbackTimer) {
    window.clearTimeout(fallbackTimer);
    fallbackTimer = null;
  }
}

function startFallbackTimer(channelId) {
  const loading = document.getElementById('watch-loading');
  if (loading) loading.hidden = false;

  fallbackTimer = window.setTimeout(() => {
    if (!playerReady) {
      if (loading) loading.hidden = true;
      showPlaybackFallback(channelId);
    }
  }, readyTimeoutMs);
}

function renderNotFound() {
  container.innerHTML = `
    <article class="panel watch-details">
      <h2>Video not found</h2>
      <p class="small">This video is not available in KidTube yet. Try refreshing the feed and come back.</p>
    </article>
  `;
}

function embedUrl(videoId) {
  const params = new URLSearchParams({
    autoplay: '0',
    rel: '0',
    modestbranding: '1',
    iv_load_policy: '3',
    playsinline: '1',
    enablejsapi: '1',
    origin: embedOrigin || window.location.origin,
  });

  return `https://www.youtube-nocookie.com/embed/${encodeURIComponent(videoId)}?${params.toString()}`;
}

async function loadVideo() {
  if (!youtubeId) {
    renderNotFound();
    return;
  }

  try {
    const video = await requestJson(`/api/videos/${youtubeId}`);
    const channelId = video.channel_youtube_id || '';
    container.innerHTML = `
      <section class="player-wrap panel">
        <iframe
          id="watch-player"
          src="${embedUrl(video.youtube_id)}"
          title="${escapeHtml(video.title)}"
          allow="autoplay; encrypted-media; picture-in-picture"
          sandbox="allow-scripts allow-same-origin allow-presentation"
          referrerpolicy="no-referrer"
          allowfullscreen
        ></iframe>
      </section>
      <article id="watch-loading" class="panel watch-details">
        <h2>Loading video…</h2>
        <p class="small">Please wait while KidTube prepares this player.</p>
      </article>
      <article id="watch-fallback" class="panel watch-details" hidden>
        <h2>This video can’t be played inside KidTube.</h2>
        <p class="small">Ask a parent to approve a different video.</p>
        <div class="watch-actions">
          <a class="btn-secondary" href="/">Back to Dashboard</a>
          <a class="btn-soft" data-channel-link href="${getChannelFilterHref(channelId)}">Try another video from this channel</a>
        </div>
      </article>
      <article class="panel watch-details">
        <h2>${escapeHtml(video.title)}</h2>
        <div class="channel-row">
          <img class="avatar" src="${video.channel_avatar_url || ''}" alt="" />
          <span>${escapeHtml(video.channel_title || 'Unknown channel')}</span>
        </div>
        <p class="small">Published: ${formatDate(video.published_at)}</p>
      </article>
    `;

    const onPlayerMessage = (event) => {
      if (event.origin !== 'https://www.youtube-nocookie.com' && event.origin !== 'https://www.youtube.com') {
        return;
      }
      if (typeof event.data !== 'string') return;
      if (event.data.includes('onReady')) {
        markReady();
      }
    };

    window.addEventListener('message', onPlayerMessage, { once: false });

    const iframe = document.getElementById('watch-player');
    iframe?.addEventListener('load', () => {
      try {
        iframe.contentWindow?.postMessage(JSON.stringify({ event: 'listening', id: youtubeId }), '*');
      } catch {
        // no-op
      }
    });

    startFallbackTimer(channelId);
  } catch (error) {
    renderNotFound();
    if (!String(error.message).includes('404')) {
      showToast(`Unable to load video: ${error.message}`, 'error');
    }
  }
}

loadVideo();
