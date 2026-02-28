import { formatDate, requestJson, showToast } from '/static/app.js';

const container = document.getElementById('watch-container');
const youtubeId = container?.dataset.youtubeId;
const embedOrigin = container?.dataset.embedOrigin;
const startedAt = Date.now();
let logged = false;

let ytApiPromise;

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
  return `/?channel_id=${encodeURIComponent(channelId)}`;
}

function showPlaybackFallback(channelId) {
  const fallback = document.getElementById('watch-fallback');
  const playerWrap = document.querySelector('.player-wrap');
  const loading = document.getElementById('watch-loading');
  if (loading) loading.hidden = true;
  if (playerWrap) playerWrap.hidden = true;

  if (!fallback) return;
  fallback.hidden = false;
  const filteredLink = fallback.querySelector('[data-channel-link]');
  if (filteredLink) {
    filteredLink.href = getChannelFilterHref(channelId);
  }
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
    rel: '0',
    modestbranding: '1',
    playsinline: '1',
    enablejsapi: '1',
    origin: embedOrigin || window.location.origin,
  });

  return `https://www.youtube-nocookie.com/embed/${encodeURIComponent(videoId)}?${params.toString()}`;
}

function loadYoutubeIframeApi() {
  if (window.YT?.Player) {
    return Promise.resolve(window.YT);
  }
  if (ytApiPromise) {
    return ytApiPromise;
  }

  ytApiPromise = new Promise((resolve, reject) => {
    const script = document.createElement('script');
    script.src = 'https://www.youtube.com/iframe_api';
    script.async = true;
    script.onerror = () => reject(new Error('Unable to load YouTube player API'));
    const previousReady = window.onYouTubeIframeAPIReady;
    window.onYouTubeIframeAPIReady = () => {
      if (typeof previousReady === 'function') previousReady();
      resolve(window.YT);
    };
    document.head.append(script);
  });

  return ytApiPromise;
}

async function loadVideo() {
  if (!youtubeId) {
    renderNotFound();
    return;
  }

  try {
    const video = await requestJson(`/api/videos/${youtubeId}`);
    const channelId = video.channel_id || '';
    container.innerHTML = `
      <section class="player-wrap panel">
        <div id="watch-player"></div>
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
          <a class="btn-soft" data-channel-link href="${getChannelFilterHref(channelId)}">More from this channel</a>
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

    const yt = await loadYoutubeIframeApi();
    new yt.Player('watch-player', {
      videoId: video.youtube_id,
      playerVars: {
        rel: 0,
        modestbranding: 1,
        playsinline: 1,
        enablejsapi: 1,
        origin: embedOrigin || window.location.origin,
      },
      host: 'https://www.youtube-nocookie.com',
      events: {
        onReady: () => {
          const loading = document.getElementById('watch-loading');
          if (loading) loading.hidden = true;
        },
        onError: () => showPlaybackFallback(channelId),
      },
    });
  } catch (error) {
    renderNotFound();
    if (!String(error.message).includes('404')) {
      showToast(`Unable to load video: ${error.message}`, 'error');
    }
  }
}

async function logWatch() {
  if (logged || !youtubeId) return;
  try {
    const sessionState = await requestJson('/api/session');
    if (!sessionState.kid_id) return;
    const seconds = Math.max(1, Math.round((Date.now() - startedAt) / 1000));
    await requestJson('/api/playback/log', {
      method: 'POST',
      body: JSON.stringify({ kid_id: sessionState.kid_id, youtube_id: youtubeId, seconds_watched: seconds }),
    });
    logged = true;
  } catch {
    // Ignore logging errors on unload.
  }
}

window.addEventListener('pagehide', () => {
  void logWatch();
});

loadVideo();
