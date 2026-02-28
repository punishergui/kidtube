import { formatDate, requestJson, showToast } from '/static/app.js';

const body = document.getElementById('kids-body');
const form = document.getElementById('add-kid-form');

let categories = [];

function scheduleRows(kid) {
  return `
    <div class="touch-section">
      <h4>Allowed Schedule Windows</h4>
      <div class="inline-form">
        <select data-day="${kid.id}">
          <option value="0">Mon</option><option value="1">Tue</option><option value="2">Wed</option><option value="3">Thu</option><option value="4">Fri</option><option value="5">Sat</option><option value="6">Sun</option>
        </select>
        <input type="time" data-start="${kid.id}" required />
        <input type="time" data-end="${kid.id}" required />
        <button class="btn-soft" data-add-schedule="${kid.id}" type="button">Add Window</button>
      </div>
      <div class="small" data-schedules="${kid.id}">Loading schedules...</div>
    </div>
  `;
}

function categoryLimitRows(kid) {
  const options = categories.map((c) => `<option value="${c.id}">${c.name}</option>`).join('');
  return `
    <div class="touch-section">
      <h4>Per-category Daily Limits</h4>
      <div class="inline-form">
        <select data-limit-category="${kid.id}">${options}</select>
        <input type="number" min="0" placeholder="minutes" data-limit-minutes="${kid.id}" />
        <button class="btn-soft" data-save-category-limit="${kid.id}" type="button">Save</button>
      </div>
      <div class="small" data-category-limits="${kid.id}">Loading category limits...</div>
    </div>
  `;
}

function row(kid) {
  return `
    <article class="panel admin-card kid-admin-card">
      <div class="admin-card-head">
        <h3>${kid.name}</h3>
        <span class="small">Joined ${formatDate(kid.created_at)}</span>
      </div>
      <div class="kid-admin-meta">
        ${kid.avatar_url ? `<img class="kid-avatar" src="${kid.avatar_url}" alt="${kid.name}" />` : '<span class="kid-avatar kid-initials">★</span>'}
        <label>Daily limit minutes<input data-limit="${kid.id}" type="number" min="1" value="${kid.daily_limit_minutes || ''}" /></label>
        <label>Bedtime start<input data-bedtime-start="${kid.id}" type="time" value="${kid.bedtime_start || ''}" /></label>
        <label>Bedtime end<input data-bedtime-end="${kid.id}" type="time" value="${kid.bedtime_end || ''}" /></label>
      </div>
      <div class="touch-section">
        <h4>Bonus Time</h4>
        <div class="inline-form">
          <input data-bonus-minutes="${kid.id}" type="number" min="1" placeholder="minutes" />
          <input data-bonus-expiry="${kid.id}" type="datetime-local" />
          <button class="btn-soft" data-add-bonus="${kid.id}" type="button">Add Bonus</button>
        </div>
        <div class="small" data-bonus-list="${kid.id}">Loading bonus time...</div>
      </div>
      ${scheduleRows(kid)}
      ${categoryLimitRows(kid)}
      <div class="avatar-upload-row">
        <input data-avatar-file="${kid.id}" type="file" accept="image/png,image/jpeg,image/webp" />
        <button class="btn-soft" data-upload-avatar="${kid.id}">Upload avatar</button>
        <button class="btn-secondary" data-remove-avatar="${kid.id}">Remove avatar</button>
      </div>
      <button class="btn-primary" data-save="${kid.id}">Save Kid Settings</button>
    </article>
  `;
}

async function fillKidExtras(kidId) {
  const [bonus, schedules, categoryLimits] = await Promise.all([
    requestJson(`/api/kids/${kidId}/bonus-time`),
    requestJson(`/api/kids/${kidId}/schedules`),
    requestJson(`/api/kids/${kidId}/category-limits`),
  ]);

  const bonusEl = body.querySelector(`[data-bonus-list="${kidId}"]`);
  bonusEl.textContent = bonus.length ? bonus.map((item) => `${item.minutes}m (expires ${formatDate(item.expires_at)})`).join(' • ') : 'No active bonus time';

  const scheduleEl = body.querySelector(`[data-schedules="${kidId}"]`);
  scheduleEl.innerHTML = schedules.length
    ? schedules.map((s) => `<div>Day ${s.day_of_week} ${s.start_time}-${s.end_time} <button class="btn-link" data-delete-schedule="${kidId}:${s.id}" type="button">Delete</button></div>`).join('')
    : 'No windows set (all day allowed).';

  const limitsEl = body.querySelector(`[data-category-limits="${kidId}"]`);
  limitsEl.innerHTML = categoryLimits.length
    ? categoryLimits.map((l) => `<div>${l.category_name}: ${l.daily_limit_minutes} min <button class="btn-link" data-delete-category-limit="${kidId}:${l.category_id}" type="button">Delete</button></div>`).join('')
    : 'No per-category overrides.';
}

async function loadKids() {
  const kids = await requestJson('/api/kids');
  categories = await requestJson('/api/categories?include_disabled=true');

  if (!kids.length) {
    body.innerHTML = '<article class="panel empty-state">No kid profiles yet. Add one above.</article>';
    return;
  }

  body.innerHTML = kids.map(row).join('');
  for (const kid of kids) {
    await fillKidExtras(kid.id);
  }

  body.querySelectorAll('button[data-save]').forEach((button) => button.addEventListener('click', async () => {
    const id = Number(button.dataset.save);
    const payload = {
      daily_limit_minutes: Number(body.querySelector(`input[data-limit="${id}"]`)?.value || 0) || null,
      bedtime_start: body.querySelector(`input[data-bedtime-start="${id}"]`)?.value || null,
      bedtime_end: body.querySelector(`input[data-bedtime-end="${id}"]`)?.value || null,
    };
    await requestJson(`/api/kids/${id}`, { method: 'PATCH', body: JSON.stringify(payload) });
    showToast('Kid settings updated.');
  }));

  body.querySelectorAll('button[data-add-bonus]').forEach((button) => button.addEventListener('click', async () => {
    const id = Number(button.dataset.addBonus);
    const minutes = Number(body.querySelector(`input[data-bonus-minutes="${id}"]`)?.value || 0);
    const expiresRaw = body.querySelector(`input[data-bonus-expiry="${id}"]`)?.value;
    await requestJson(`/api/kids/${id}/bonus-time`, { method: 'POST', body: JSON.stringify({ minutes, expires_at: expiresRaw ? new Date(expiresRaw).toISOString() : null }) });
    await fillKidExtras(id);
    showToast('Bonus time added.');
  }));

  body.querySelectorAll('button[data-add-schedule]').forEach((button) => button.addEventListener('click', async () => {
    const id = Number(button.dataset.addSchedule);
    await requestJson(`/api/kids/${id}/schedules`, {
      method: 'POST',
      body: JSON.stringify({
        day_of_week: Number(body.querySelector(`select[data-day="${id}"]`)?.value || 0),
        start_time: body.querySelector(`input[data-start="${id}"]`)?.value,
        end_time: body.querySelector(`input[data-end="${id}"]`)?.value,
      }),
    });
    await fillKidExtras(id);
    showToast('Schedule window added.');
  }));

  body.querySelectorAll('button[data-save-category-limit]').forEach((button) => button.addEventListener('click', async () => {
    const id = Number(button.dataset.saveCategoryLimit);
    const categoryId = Number(body.querySelector(`select[data-limit-category="${id}"]`)?.value);
    const minutes = Number(body.querySelector(`input[data-limit-minutes="${id}"]`)?.value || 0);
    await requestJson(`/api/kids/${id}/category-limits/${categoryId}`, { method: 'PUT', body: JSON.stringify({ daily_limit_minutes: minutes }) });
    await fillKidExtras(id);
    showToast('Category limit saved.');
  }));

  body.querySelectorAll('button[data-delete-schedule]').forEach((button) => button.addEventListener('click', async () => {
    const [kidId, scheduleId] = button.dataset.deleteSchedule.split(':').map(Number);
    await requestJson(`/api/kids/${kidId}/schedules/${scheduleId}`, { method: 'DELETE' });
    await fillKidExtras(kidId);
  }));

  body.querySelectorAll('button[data-delete-category-limit]').forEach((button) => button.addEventListener('click', async () => {
    const [kidId, categoryId] = button.dataset.deleteCategoryLimit.split(':').map(Number);
    await requestJson(`/api/kids/${kidId}/category-limits/${categoryId}`, { method: 'DELETE' });
    await fillKidExtras(kidId);
  }));

  body.querySelectorAll('button[data-upload-avatar]').forEach((button) => {
    button.addEventListener('click', async () => {
      const id = Number(button.dataset.uploadAvatar);
      const file = body.querySelector(`input[data-avatar-file="${id}"]`)?.files?.[0];
      if (!file) return;
      const formData = new FormData();
      formData.append('file', file);
      await fetch(`/api/kids/${id}/avatar`, { method: 'POST', body: formData });
      await loadKids();
    });
  });

  body.querySelectorAll('button[data-remove-avatar]').forEach((button) => button.addEventListener('click', async () => {
    const id = Number(button.dataset.removeAvatar);
    await requestJson(`/api/kids/${id}/avatar`, { method: 'DELETE' });
    await loadKids();
  }));
}

form.addEventListener('submit', async (event) => {
  event.preventDefault();
  const data = new FormData(form);
  await requestJson('/api/kids', {
    method: 'POST',
    body: JSON.stringify({
      name: String(data.get('name') || '').trim(),
      daily_limit_minutes: Number(String(data.get('daily_limit_minutes') || '').trim()) || null,
      bedtime_start: String(data.get('bedtime_start') || '').trim() || null,
      bedtime_end: String(data.get('bedtime_end') || '').trim() || null,
    }),
  });
  form.reset();
  await loadKids();
  showToast('Kid created.');
});

loadKids().catch((error) => showToast(`Unable to load kids: ${error.message}`, 'error'));
