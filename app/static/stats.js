import { formatDate, requestJson, showToast } from '/static/app.js';

const kidFilter = document.getElementById('stats-kid-filter');
const refreshBtn = document.getElementById('refresh-stats');
const summary = document.getElementById('stats-summary');
const categoriesWrap = document.getElementById('stats-categories');
const watchLogsWrap = document.getElementById('watch-logs');
const searchLogsWrap = document.getElementById('search-logs');

function asMinutes(seconds) {
  return `${Math.round((Number(seconds || 0) / 60) * 10) / 10} min`;
}

function renderTable(rows, headers) {
  if (!rows.length) return '<article class="empty-state">No data yet.</article>';
  const head = headers.map((h) => `<th>${h}</th>`).join('');
  const body = rows
    .map((row) => `<tr>${row.map((cell) => `<td>${cell}</td>`).join('')}</tr>`)
    .join('');
  return `<table><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table>`;
}

async function load() {
  try {
    const kidId = kidFilter.value;
    const [kids, stats, watchLogs, searchLogs] = await Promise.all([
      requestJson('/api/kids'),
      requestJson(`/api/stats${kidId ? `?kid_id=${kidId}` : ''}`),
      requestJson(`/api/logs/recent?limit=40${kidId ? `&kid_id=${kidId}` : ''}`),
      requestJson(`/api/logs/search?limit=40${kidId ? `&kid_id=${kidId}` : ''}`),
    ]);

    if (!kidFilter.dataset.ready) {
      kidFilter.innerHTML = '<option value="">All kids</option>' + kids.map((kid) => `<option value="${kid.id}">${kid.name}</option>`).join('');
      kidFilter.dataset.ready = '1';
      if (kidId) kidFilter.value = kidId;
    }

    summary.innerHTML = `
      <div class="sync-stats">
        <article class="panel stat-card"><strong>Today</strong><p>${asMinutes(stats.today_seconds)}</p></article>
        <article class="panel stat-card"><strong>Lifetime</strong><p>${asMinutes(stats.lifetime_seconds)}</p></article>
        <article class="panel stat-card"><strong>Categories watched</strong><p>${stats.categories.length}</p></article>
      </div>
    `;

    categoriesWrap.innerHTML = renderTable(
      stats.categories.map((entry) => [entry.category_name || 'Uncategorized', asMinutes(entry.today_seconds), asMinutes(entry.lifetime_seconds)]),
      ['Category', 'Today', 'Lifetime'],
    );

    watchLogsWrap.innerHTML = renderTable(
      watchLogs.map((row) => [row.kid_name || row.kid_id, row.video_title || 'Unknown', row.channel_title || 'Unknown channel', row.category_name || 'Uncategorized', asMinutes(row.seconds_watched), formatDate(row.created_at)]),
      ['Kid', 'Video', 'Channel', 'Category', 'Watched', 'At'],
    );

    searchLogsWrap.innerHTML = renderTable(
      searchLogs.map((row) => [row.kid_name || row.kid_id, row.query, formatDate(row.created_at)]),
      ['Kid', 'Query', 'At'],
    );
  } catch (error) {
    showToast(`Unable to load logs/stats: ${error.message}`, 'error');
  }
}

refreshBtn?.addEventListener('click', load);
kidFilter?.addEventListener('change', load);
load();
