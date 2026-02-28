import { formatDate, requestJson, showToast } from '/static/app.js';

const container = document.getElementById('watch-container');
const youtubeId = container?.dataset.youtubeId;
const embedOrigin = container?.dataset.embedOrigin;
let accumulatedSeconds = 0;
let lastTick = Date.now();
let kidId = null;
let flushBusy = false;
let heartbeatHandle = null;

let ytApiPromise;

const embedBase = 'https://www.youtube-nocookie.com/embed';
const playerMode = new URLSearchParams(window.location.search).get('mode');

function buildNoCookieEmbedUrl(videoId) {
  const params = new URLSearchParams({
    rel: '0',
    modestbranding: '1',
    playsinline: '1',
    enablejsapi: '1',
    origin: embedOrigin || window.location.origin,
  });
  return `${embedBase}/${encodeURIComponent(videoId)}?${params.toString()}`;
}

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

function loadYoutubeIframeApi() {
  if (window.YT?.Player) return Promise.resolve(window.YT);
  if (ytApiPromise) return ytApiPromise;

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

function accrueWatchTime() {
  const now = Date.now();
  accumulatedSeconds += Math.max(0, Math.floor((now - lastTick) / 1000));
  lastTick = now;
}

async function flushWatchLog(force = false) {
  if (!youtubeId || !kidId || flushBusy) return;
  if (!force && accumulatedSeconds < 10) return;
  const delta = Math.max(1, accumulatedSeconds);
  accumulatedSeconds = 0;
  flushBusy = true;
  try {
    await requestJson('/api/playback/watch/log', {
      method: 'POST',
      body: JSON.stringify({ kid_id: kidId, video_id: youtubeId, seconds_delta: delta, is_playing: true }),
    });
  } catch {
    // no-op
  } finally {
    flushBusy = false;
  }
}

function updateNowPlaying(kid, minutesLeftText) {
  const overlay = document.getElementById('watch-now-playing');
  if (!overlay) return;

  const avatar = document.getElementById('watch-now-playing-avatar');
  const kidName = document.getElementById('watch-now-playing-name');
  const minutesLeft = document.getElementById('watch-now-playing-minutes');

  if (avatar) avatar.src = kid?.avatar_url || '';
  if (kidName) kidName.textContent = kid?.name || 'Kid';
  if (minutesLeft) minutesLeft.textContent = minutesLeftText;
  overlay.hidden = false;
}

async function loadNowPlaying(sessionState) {
  if (!sessionState?.kid_id) {
    updateNowPlaying(null, 'Session unavailable');
    return;
  }

  let kid = null;
  let minutesLeftText = 'Time left unavailable';

  try {
    const kids = await requestJson('/api/kids');
    kid = (kids || []).find((k) => k.id === sessionState.kid_id) || null;
  } catch {
    // no-op
  }

  try {
    const limits = await requestJson(`/api/kids/${sessionState.kid_id}/limits`);
    if (typeof limits.remaining_seconds === 'number') {
      const minutes = Math.max(0, Math.floor(limits.remaining_seconds / 60));
      minutesLeftText = `${minutes} min left today`;
    }
  } catch {
    // no-op
  }

  updateNowPlaying(kid, minutesLeftText);
}

async function loadVideo() {
  if (playerMode === 'shorts') {
    container.classList.add('shorts-mode');
  }

  if (!youtubeId) {
    renderNotFound();
    return;
  }

  try {
    const sessionState = await requestJson('/api/session');
    kidId = sessionState.kid_id || null;
    const video = await requestJson(`/api/videos/${youtubeId}?kid_id=${kidId || ''}`);
    const channelId = video.channel_id || '';
    container.innerHTML = `
      <section class="player-wrap panel">
        <div id="watch-player"></div>
        <div id="watch-now-playing" class="watch-now-playing" hidden>
          <div class="watch-now-playing-left">
            <img id="watch-now-playing-avatar" class="watch-now-playing-avatar" alt="" src="" />
            <div class="watch-now-playing-meta">
              <strong id="watch-now-playing-name">Kid</strong>
              <span id="watch-now-playing-minutes">Loading time left…</span>
            </div>
          </div>
          <a class="btn-secondary" href="/dashboard">Home</a>
        </div>
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

    await loadNowPlaying(sessionState);

    heartbeatHandle = window.setInterval(async () => {
      accrueWatchTime();
      await flushWatchLog(false);
    }, 12000);

    const yt = await loadYoutubeIframeApi();
    const player = new yt.Player('watch-player', {
      videoId: video.youtube_id,
      playerVars: { rel: 0, modestbranding: 1, playsinline: 1, enablejsapi: 1, origin: embedOrigin || window.location.origin },
      host: 'https://www.youtube-nocookie.com',
      events: {
        onReady: () => {
          const loading = document.getElementById('watch-loading');
          if (loading) loading.hidden = true;
          const iframe = player.getIframe?.();
          if (iframe) iframe.src = buildNoCookieEmbedUrl(video.youtube_id);
        },
        onError: () => showPlaybackFallback(channelId),
        onStateChange: async (event) => {
          if (event.data === window.YT.PlayerState.PAUSED || event.data === window.YT.PlayerState.ENDED) {
            accrueWatchTime();
            await flushWatchLog(true);
          }
        },
      },
    });
  } catch (error) {
    renderNotFound();
    if (!String(error.message).includes('404')) showToast(`Unable to load video: ${error.message}`, 'error');
  }
}

window.addEventListener('visibilitychange', () => {
  if (document.hidden) {
    accrueWatchTime();
    void flushWatchLog(true);
  } else {
    lastTick = Date.now();
  }
});

window.addEventListener('pagehide', () => {
  accrueWatchTime();
  if (kidId && youtubeId && accumulatedSeconds > 0) {
    const delta = Math.max(1, accumulatedSeconds);
    accumulatedSeconds = 0;
    navigator.sendBeacon('/api/playback/watch/log', JSON.stringify({
      kid_id: kidId,
      video_id: youtubeId,
      seconds_delta: delta,
      is_playing: true,
    }));
  }
  if (heartbeatHandle) window.clearInterval(heartbeatHandle);
});

loadVideo();
