import { requestJson, showToast } from '/static/app.js';

const runButton = document.getElementById('run-sync');
const result = document.getElementById('sync-result');

runButton.addEventListener('click', async () => {
  runButton.disabled = true;
  result.innerHTML = '<p>Sync in progress...</p>';

  try {
    const response = await requestJson('/api/sync/run', { method: 'POST', body: '{}' });
    const updatedAt = new Date().toLocaleString();
    const failures = response.failures?.length
      ? `<table><thead><tr><th>Channel ID</th><th>Input</th><th>Error</th></tr></thead><tbody>${response.failures
          .map(
            (failure) => `<tr><td>#${failure.id ?? '—'}</td><td>${failure.input || '—'}</td><td>${failure.error}</td></tr>`,
          )
          .join('')}</tbody></table>`
      : '<p>No failures 🎉</p>';

    result.innerHTML = `
      <div class="sync-stats">
        <p><strong>channels_seen:</strong> ${response.channels_seen}</p>
        <p><strong>resolved:</strong> ${response.resolved}</p>
        <p><strong>synced:</strong> ${response.synced}</p>
        <p><strong>failed:</strong> ${response.failed}</p>
      </div>
      <p class="small">Updated at ${updatedAt}</p>
      <h3>Failures</h3>
      ${failures}
      <p class="sync-actions"><a href="/" class="btn-secondary">Back to Kid Dashboard</a></p>
    `;

    localStorage.setItem('kidtube-refresh-feed-once', '1');
    showToast('Sync completed successfully.');
  } catch (error) {
    showToast(`Sync failed: ${error.message}`, 'error');
    result.innerHTML = '<p class="status error">Sync failed. Please try again.</p>';
  } finally {
    runButton.disabled = false;
  }
});
