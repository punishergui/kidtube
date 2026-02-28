import { formatDate, requestJson, showToast } from '/static/app.js';

const kidFilter = document.getElementById('stats-kid-filter');
const refreshBtn = document.getElementById('refresh-stats');
const summary = document.getElementById('stats-summary');
const dailySummary = document.getElementById('today-summary');
const categoriesWrap = document.getElementById('stats-categories');
const watchLogsWrap = document.getElementById('watch-logs');
const searchLogsWrap = document.getElementById('search-logs');
const categoryChartCanvas = document.getElementById('category-breakdown-chart');

let categoryChart = null;

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

function renderTodaySummary(rows) {
  if (!rows.length) {
    dailySummary.innerHTML = '<article class="empty-state">No kid profiles yet.</article>';
    return;
  }

  dailySummary.innerHTML = `
    <h2>Today's Summary</h2>
    <div class="today-summary-grid">
      ${rows
        .map((row) => {
          const total = Number(row.total_minutes_today || 0);
          const education = Number(row.education_minutes_today || 0);
          const fun = Number(row.fun_minutes_today || 0);
          const eduPct = total > 0 ? Math.min(100, (education / total) * 100) : 0;
          const funPct = total > 0 ? Math.min(100, (fun / total) * 100) : 0;
          return `
            <article class="today-kid-card">
              <h3>${row.kid_name}</h3>
              <p><strong>Total:</strong> ${total} min</p>
              <div class="split-bar">
                <span class="split-edu" style="width:${eduPct}%"></span>
                <span class="split-fun" style="width:${funPct}%"></span>
              </div>
              <p class="small">Education ${education}m · Fun ${fun}m</p>
              <div>
                <strong>Top channels</strong>
                <ul>
                  ${(row.top_channels || [])
                    .map((channel) => `<li>${channel.title} (${channel.minutes}m)</li>`)
                    .join('') || '<li>No watch data today</li>'}
                </ul>
              </div>
              <p><strong>Denied requests:</strong> ${row.denied_requests_today}</p>
              <p><strong>Searches:</strong> ${row.searches_today}</p>
            </article>
          `;
        })
        .join('')}
    </div>
  `;
}

function renderCategoryChart(stats) {
  if (!categoryChartCanvas || typeof window.Chart === 'undefined') return;
  const totals = new Map();
  for (const row of stats.categories || []) {
    const name = row.category_name || 'Uncategorized';
    const prev = totals.get(name) || 0;
    totals.set(name, prev + Number(row.today_seconds || 0));
  }

  const labels = [...totals.keys()];
  const values = labels.map((name) => Math.round((totals.get(name) / 60) * 10) / 10);

  if (categoryChart) categoryChart.destroy();
  categoryChart = new window.Chart(categoryChartCanvas, {
    type: 'bar',
    data: {
      labels,
      datasets: [
        {
          label: 'Minutes watched today',
          data: values,
          backgroundColor: ['#5f6dff', '#ff76c8', '#56cfe1', '#f7b801', '#72efdd', '#80ed99'],
        },
      ],
    },
    options: {
      responsive: true,
      plugins: {
        legend: { display: false },
      },
      scales: {
        y: {
          beginAtZero: true,
          ticks: { color: '#e6edf3' },
          grid: { color: '#30363d' },
        },
        x: {
          ticks: { color: '#e6edf3' },
          grid: { color: '#30363d' },
        },
      },
    },
  });
}

async function load() {
  try {
    const kidId = kidFilter.value;
    const [kids, stats, watchLogs, searchLogs, daily] = await Promise.all([
      requestJson('/api/kids'),
      requestJson(`/api/stats${kidId ? `?kid_id=${kidId}` : ''}`),
      requestJson(`/api/logs/recent?limit=40${kidId ? `&kid_id=${kidId}` : ''}`),
      requestJson(`/api/logs/search?limit=40${kidId ? `&kid_id=${kidId}` : ''}`),
      requestJson('/api/stats/daily-summary'),
    ]);

    if (!kidFilter.dataset.ready) {
      kidFilter.innerHTML =
        '<option value="">All kids</option>' +
        kids.map((kid) => `<option value="${kid.id}">${kid.name}</option>`).join('');
      kidFilter.dataset.ready = '1';
      if (kidId) kidFilter.value = kidId;
    }

    renderTodaySummary(daily);

    summary.innerHTML = `
      <div class="sync-stats">
        <article class="panel stat-card"><strong>Today</strong><p>${asMinutes(stats.today_seconds)}</p></article>
        <article class="panel stat-card"><strong>Lifetime</strong><p>${asMinutes(stats.lifetime_seconds)}</p></article>
        <article class="panel stat-card"><strong>Categories watched</strong><p>${stats.categories.length}</p></article>
      </div>
    `;

    categoriesWrap.innerHTML = renderTable(
      stats.categories.map((entry) => [
        entry.category_name || 'Uncategorized',
        asMinutes(entry.today_seconds),
        asMinutes(entry.lifetime_seconds),
      ]),
      ['Category', 'Today', 'Lifetime'],
    );

    renderCategoryChart(stats);

    watchLogsWrap.innerHTML = renderTable(
      watchLogs.map((row) => [
        row.kid_name || row.kid_id,
        row.video_title || 'Unknown',
        row.channel_title || 'Unknown channel',
        row.category_name || 'Uncategorized',
        asMinutes(row.seconds_watched),
        formatDate(row.created_at),
      ]),
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
