import { formatDate, requestJson, showToast } from '/static/app.js';

const grid = document.getElementById('dashboard-grid');
const latestGrid = document.getElementById('latest-channel-grid');
const kidSelector = document.getElementById('kid-selector');
const categoryPills = document.getElementById('category-pills');
const moreButton = document.getElementById('see-more-btn');
const parentControlNote = document.getElementById('parent-control-note');

const categories = ['all', 'education', 'fun'];
const queryParams = new URLSearchParams(window.location.search);

const state = {
  items: [],
  latestPerChannel: [],
  kids: [],
  category: localStorage.getItem('kidtube-category') || 'all',
  kidId: Number(localStorage.getItem('kidtube-active-kid')) || null,
  channelFilter: queryParams.get('channel_id') || null,
  offset: 0,
  limit: 30,
  hasMore: true,
};

function formatDuration(seconds) {
  if (!Number.isFinite(seconds) || seconds <= 0) return '5:00';
  const mins = Math.floor(seconds / 60);
  const secs = seconds % 60;
  return `${mins}:${String(secs).padStart(2, '0')}`;
}

function normalizeCategory(item) {
  const value = String(item.channel_category || item.category || '').toLowerCase();
  if (value.includes('education') || value.includes('science')) return 'education';
  return 'fun';
}

function categoryMatches(item) {
  if (state.category !== 'all' && normalizeCategory(item) !== state.category) return false;
  if (state.channelFilter && String(item.channel_id) !== String(state.channelFilter)) return false;
  return true;
}

function renderCategories() {
  categoryPills.innerHTML = categories
    .map((category) => {
      const active = category === state.category;
      return `<button class="pill ${active ? 'active' : ''}" data-category="${category}" role="tab" aria-selected="${active}">${category[0].toUpperCase()}${category.slice(1)}</button>`;
    })
    .join('');

  categoryPills.querySelectorAll('button[data-category]').forEach((button) => {
    button.addEventListener('click', () => {
      state.category = button.dataset.category;
      localStorage.setItem('kidtube-category', state.category);
      renderCategories();
      renderVideos();
    });
  });
}

function kidCard(kid) {
  const isActive = kid.id === state.kidId;
  const initials = kid.name
    .split(' ')
    .map((part) => part[0])
    .join('')
    .slice(0, 2)
    .toUpperCase();

  return `
    <button class="kid-chip ${isActive ? 'active' : ''}" data-kid-id="${kid.id}">
      <span class="kid-avatar-wrap">
        ${kid.avatar_url ? `<img class="kid-avatar" src="${kid.avatar_url}" alt="${kid.name}" />` : `<span class="kid-avatar kid-initials">${initials}</span>`}
      </span>
      <span class="kid-meta">
        <strong>${kid.name}</strong>
        <span class="left-pill">${kid.daily_limit_minutes || 60}m left</span>
      </span>
    </button>
  `;
}

function renderKids(kids) {
  if (!kids.length) {
    kidSelector.innerHTML = '<article class="empty-state">No kid profiles yet. Visit the Kids page to add one.</article>';
    return;
  }

  if (!state.kidId || !kids.find((kid) => kid.id === state.kidId)) {
    state.kidId = kids[0].id;
  }

  kidSelector.innerHTML = kids.map(kidCard).join('');

  kidSelector.querySelectorAll('[data-kid-id]').forEach((button) => {
    button.addEventListener('click', () => {
      state.kidId = Number(button.dataset.kidId);
      localStorage.setItem('kidtube-active-kid', String(state.kidId));
      state.items = [];
      state.offset = 0;
      state.hasMore = true;
      loadDashboard().catch((error) => showToast(`Unable to refresh feed: ${error.message}`, 'error'));
    });
  });
}

function card(item) {
  return `
    <a class="video-card panel" href="/watch/${item.video_youtube_id}">
      <div class="video-thumb-wrap">
        <img class="thumb" src="${item.video_thumbnail_url}" alt="${item.video_title}" loading="lazy" />
        <span class="duration-badge">${formatDuration(item.video_duration_seconds)}</span>
        <img class="channel-stamp" src="${item.channel_avatar_url || ''}" alt="" />
      </div>
      <div class="video-card-body">
        <h3 class="video-title">${item.video_title}</h3>
        <p class="channel-name">${item.channel_title || 'Unknown channel'}</p>
        <p class="small">${formatDate(item.video_published_at)}</p>
      </div>
    </a>
  `;
}

function renderParentControlNote() {
  const activeKid = state.kids.find((kid) => kid.id === state.kidId);
  if (!activeKid || !parentControlNote) {
    return;
  }

  const hasControls = Boolean(
    activeKid.require_parent_approval ||
    activeKid.bedtime_start ||
    activeKid.bedtime_end ||
    activeKid.daily_limit_minutes ||
    activeKid.weekend_bonus_minutes,
  );

  if (!hasControls) {
    parentControlNote.hidden = true;
    parentControlNote.textContent = '';
    return;
  }

  parentControlNote.hidden = false;
  const chunks = [];
  if (activeKid.daily_limit_minutes) chunks.push(`Daily limit ${activeKid.daily_limit_minutes}m`);
  if (activeKid.weekend_bonus_minutes) chunks.push(`Weekend +${activeKid.weekend_bonus_minutes}m`);
  if (activeKid.bedtime_start && activeKid.bedtime_end) {
    chunks.push(`Bedtime ${activeKid.bedtime_start}-${activeKid.bedtime_end}`);
  }
  if (activeKid.require_parent_approval) chunks.push('Parent approval on');

  parentControlNote.textContent = `Parent controls for ${activeKid.name}: ${chunks.join(' • ')}`;
}

function renderVideos() {
  const visible = state.items.filter(categoryMatches);
  if (!visible.length) {
    grid.innerHTML = '<article class="panel empty-state">No videos in this category yet. Try another filter!</article>';
  } else {
    grid.innerHTML = visible.map(card).join('');
  }

  renderParentControlNote();

  if (latestGrid) {
    latestGrid.innerHTML = state.latestPerChannel.length
      ? state.latestPerChannel.map(card).join('')
      : '<article class="panel empty-state">No latest-per-channel videos yet.</article>';
  }
}

async function loadMore() {
  if (!state.hasMore) return;

  const params = new URLSearchParams({ limit: String(state.limit), offset: String(state.offset) });
  if (state.channelFilter) params.set('channel_id', state.channelFilter);
  if (state.category !== 'all') params.set('category', state.category);
  if (state.kidId) params.set('kid_id', String(state.kidId));

  const page = await requestJson(`/api/feed?${params.toString()}`);
  state.items.push(...page);
  state.offset += page.length;
  state.hasMore = page.length === state.limit;

  if (moreButton) {
    moreButton.hidden = !state.hasMore;
    moreButton.disabled = false;
  }

  renderVideos();
}

async function loadDashboard() {
  try {
    const kids = await requestJson('/api/kids');
    state.kids = kids;
    renderKids(kids);

    const latestParams = new URLSearchParams();
    if (state.kidId) latestParams.set('kid_id', String(state.kidId));
    const latest = await requestJson(`/api/feed/latest-per-channel?${latestParams.toString()}`);
    state.latestPerChannel = latest;
    renderCategories();
    await loadMore();
  } catch (error) {
    showToast(`Unable to load feed: ${error.message}`, 'error');
  }
}

moreButton?.addEventListener('click', async () => {
  moreButton.disabled = true;
  await loadMore();
});

loadDashboard();
