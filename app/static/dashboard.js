import { formatDate, requestJson, showToast } from '/static/app.js';

const grid = document.getElementById('dashboard-grid');
const kidSelector = document.getElementById('kid-selector');
const categoryPills = document.getElementById('category-pills');

const categories = ['all', 'education', 'fun'];
const state = {
  items: [],
  category: localStorage.getItem('kidtube-category') || 'all',
  kidId: Number(localStorage.getItem('kidtube-active-kid')) || null,
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
  if (state.category === 'all') return true;
  return normalizeCategory(item) === state.category;
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
      renderKids(kids);
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

function renderVideos() {
  const visible = state.items.filter(categoryMatches);
  if (!visible.length) {
    grid.innerHTML = '<article class="panel empty-state">No videos in this category yet. Try another filter!</article>';
    return;
  }

  grid.innerHTML = visible.map(card).join('');
}

async function loadDashboard() {
  try {
    const [items, kids] = await Promise.all([requestJson('/api/feed/latest-per-channel'), requestJson('/api/kids')]);
    state.items = items;
    renderKids(kids);
    renderCategories();
    renderVideos();
  } catch (error) {
    showToast(`Unable to load feed: ${error.message}`, 'error');
  }
}

loadDashboard();
