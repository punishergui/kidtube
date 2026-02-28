import { formatDate, requestJson, showToast } from '/static/app.js';

const grid = document.getElementById('dashboard-grid');
const latestGrid = document.getElementById('latest-channel-grid');
const kidSelector = document.getElementById('kid-selector');
const categoryPills = document.getElementById('category-pills');
const moreButton = document.getElementById('see-more-btn');
const pinGate = document.getElementById('pin-gate');
const pinInput = document.getElementById('pin-input');
const pinSubmit = document.getElementById('pin-submit');
const pinCancel = document.getElementById('pin-cancel');
const pinError = document.getElementById('pin-error');
const categoryPanel = document.getElementById('category-panel');
const newAdventures = document.getElementById('new-adventures');
const latestVideos = document.getElementById('latest-videos');
const searchResultsWrap = document.getElementById('search-results');
const searchResultsGrid = document.getElementById('search-results-grid');
const allowedChannelGrid = document.getElementById('allowed-channel-grid');
const shortsGrid = document.getElementById('shorts-grid');

const categories = ['all', 'education', 'fun'];
const queryParams = new URLSearchParams(window.location.search);

const state = { items: [], latestPerChannel: [], kids: [], allowedChannels: [], shorts: [], category: 'all', kidId: null, pendingKidId: null, channelFilter: queryParams.get('channel_id') || null, offset: 0, limit: 30, hasMore: true, searchResults: [] };

function setFeedVisible(visible) { categoryPanel.hidden = !visible; newAdventures.hidden = !visible; latestVideos.hidden = !visible; }
function formatDuration(seconds) { if (!Number.isFinite(seconds) || seconds <= 0) return '5:00'; const mins = Math.floor(seconds / 60); const secs = seconds % 60; return `${mins}:${String(secs).padStart(2, '0')}`; }
function normalizeCategory(item) { const value = String(item.channel_category || item.category || '').toLowerCase(); if (value.includes('education') || value.includes('science')) return 'education'; return 'fun'; }
function categoryMatches(item) { if (state.category !== 'all' && normalizeCategory(item) !== state.category) return false; if (state.channelFilter && String(item.channel_id) !== String(state.channelFilter)) return false; return true; }

function renderCategories() { categoryPills.innerHTML = categories.map((category) => `<button class="pill ${category === state.category ? 'active' : ''}" data-category="${category}">${category[0].toUpperCase()}${category.slice(1)}</button>`).join(''); categoryPills.querySelectorAll('button[data-category]').forEach((button) => button.addEventListener('click', () => { state.category = button.dataset.category; renderCategories(); renderVideos(); })); }
function kidCard(kid) { const isActive = kid.id === state.kidId || kid.id === state.pendingKidId; const initials = kid.name.split(' ').map((part) => part[0]).join('').slice(0, 2).toUpperCase(); return `<button class="kid-chip ${isActive ? 'active' : ''}" data-kid-id="${kid.id}">${kid.avatar_url ? `<img class="kid-avatar" src="${kid.avatar_url}" alt="${kid.name}" />` : `<span class="kid-avatar kid-initials">${initials}</span>`}<strong>${kid.name}</strong></button>`; }

function renderKids() { if (!state.kids.length) { kidSelector.innerHTML = '<article class="empty-state">No kid profiles yet.</article>'; return; } kidSelector.innerHTML = state.kids.map(kidCard).join(''); kidSelector.querySelectorAll('[data-kid-id]').forEach((button) => button.addEventListener('click', async () => { const payload = await requestJson('/api/session/kid', { method: 'POST', body: JSON.stringify({ kid_id: Number(button.dataset.kidId) }) }); state.pendingKidId = payload.pin_required ? payload.kid_id : null; state.kidId = payload.pin_required ? null : payload.kid_id; pinGate.hidden = !payload.pin_required; if (!payload.pin_required) await loadFeedData(); renderKids(); })); }
function card(item, isShort = false) { return `<a class="video-card panel ${isShort ? 'short-card' : ''}" href="/watch/${item.video_youtube_id}"><img class="thumb" src="${item.video_thumbnail_url}" alt="${item.video_title}" /><div><h3 class="video-title">${item.video_title}</h3><p class="small">${item.channel_title || 'Unknown'} · ${formatDuration(item.video_duration_seconds)}</p></div></a>`; }

function renderVideos() {
  const visible = state.items.filter(categoryMatches);
  grid.innerHTML = visible.length ? visible.map((item) => card(item)).join('') : '<article class="panel empty-state">No videos yet.</article>';
  latestGrid.innerHTML = state.latestPerChannel.length ? state.latestPerChannel.map((item) => card(item)).join('') : '<article class="panel empty-state">No latest videos yet.</article>';
  allowedChannelGrid.innerHTML = state.allowedChannels.length ? state.allowedChannels.map((channel) => `<a class="panel" href="/channel/${channel.youtube_id}"><p>${channel.title || channel.youtube_id}</p></a>`).join('') : '<article class="panel empty-state">No allowed channels.</article>';
  shortsGrid.innerHTML = state.shorts.length ? state.shorts.map((item) => card(item, true)).join('') : '<article class="panel empty-state">No shorts right now.</article>';
}

function renderSearchResults() {
  searchResultsWrap.hidden = !state.searchResults.length;
  if (!state.searchResults.length) return;
  searchResultsGrid.innerHTML = state.searchResults.map((item) => `
    <article class="panel video-card">
      <img class="thumb" src="${item.thumbnail_url}" alt="${item.title}" />
      <div><h3 class="video-title">${item.title}</h3><p class="small">${item.channel_title}</p>
      <button class="btn-primary" data-request-video="${item.video_id}" data-request-channel="${item.channel_id || ''}">Request</button></div>
    </article>`).join('');
  searchResultsGrid.querySelectorAll('[data-request-video]').forEach((button) => button.addEventListener('click', async () => {
    if (!state.kidId) return;
    const channelId = button.dataset.requestChannel;
    const channelAllowed = state.allowedChannels.some((channel) => channel.youtube_id === channelId);
    if (channelId && !channelAllowed) {
      await requestJson('/api/requests/channel-allow', { method: 'POST', body: JSON.stringify({ youtube_id: channelId, kid_id: state.kidId }) });
    } else {
      await requestJson('/api/requests/video-allow', { method: 'POST', body: JSON.stringify({ youtube_id: button.dataset.requestVideo, kid_id: state.kidId }) });
    }
    showToast('Request sent to parent');
  }));
}

async function loadMore() { if (!state.hasMore) return; const params = new URLSearchParams({ limit: String(state.limit), offset: String(state.offset) }); if (state.channelFilter) params.set('channel_id', state.channelFilter); if (state.kidId) params.set('kid_id', String(state.kidId)); const page = await requestJson(`/api/feed?${params.toString()}`); state.items.push(...page); state.offset += page.length; state.hasMore = page.length === state.limit; if (moreButton) moreButton.hidden = !state.hasMore; renderVideos(); }

async function loadFeedData() {
  if (!state.kidId) { setFeedVisible(false); return; }
  pinGate.hidden = true; setFeedVisible(true); state.items = []; state.offset = 0; state.hasMore = true;
  [state.latestPerChannel, state.allowedChannels, state.shorts] = await Promise.all([
    requestJson('/api/feed/latest-per-channel'),
    requestJson(`/api/channels/allowed?kid_id=${state.kidId}`),
    requestJson('/api/feed/shorts'),
  ]);
  await loadMore();
}

async function loadDashboard() { const [kids, sessionState] = await Promise.all([requestJson('/api/kids'), requestJson('/api/session')]); state.kids = kids; state.kidId = sessionState.kid_id; state.pendingKidId = sessionState.pending_kid_id; pinGate.hidden = !state.pendingKidId; renderKids(); renderCategories(); await loadFeedData(); }

pinSubmit?.addEventListener('click', async () => { if (pinError) pinError.hidden = true; try { const payload = await requestJson('/api/session/kid/verify-pin', { method: 'POST', body: JSON.stringify({ pin: pinInput.value }) }); state.kidId = payload.kid_id; state.pendingKidId = null; pinInput.value = ''; renderKids(); await loadFeedData(); } catch { if (pinError) pinError.hidden = false; } });
pinCancel?.addEventListener('click', () => { state.pendingKidId = null; pinGate.hidden = true; pinInput.value = ''; if (pinError) pinError.hidden = true; renderKids(); });
moreButton?.addEventListener('click', async () => { moreButton.disabled = true; await loadMore(); moreButton.disabled = false; });
window.addEventListener('kidtube:search-results', (event) => { state.searchResults = event.detail.results || []; renderSearchResults(); });

loadDashboard().catch((error) => showToast(`Unable to load dashboard: ${error.message}`, 'error'));
