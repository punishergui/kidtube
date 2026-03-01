import { requestJson, showToast } from '/static/app.js';

const runButton = document.getElementById('run-sync');
const runDeepButton = document.getElementById('run-deep-sync');
const result = document.getElementById('sync-result');

async function runSync(endpoint, modeLabel) {
  runButton.disabled = true;
  if (runDeepButton) runDeepButton.disabled = true;
  result.innerHTML = `<p>${modeLabel} in progress...</p>`;

  try {
    const response = await requestJson(endpoint, { method: 'POST', body: '{}' });
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
    showToast(`${modeLabel} completed successfully.`);
  } catch (error) {
    showToast(`${modeLabel} failed: ${error.message}`, 'error');
    result.innerHTML = `<p class="status error">${modeLabel} failed. Please try again.</p>`;
  } finally {
    runButton.disabled = false;
    if (runDeepButton) runDeepButton.disabled = false;
  }
}

runButton.addEventListener('click', async () => {
  await runSync('/api/sync/run', 'Sync');
});

runDeepButton?.addEventListener('click', async () => {
  await runSync('/api/sync/deep', 'Deep sync');
});
