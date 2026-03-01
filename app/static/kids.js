import { formatDate, requestJson, showToast } from '/static/app.js';

const body = document.getElementById('kids-body');
const form = document.getElementById('add-kid-form');

const DAYS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
let categories = [];

function scheduleGrid(kid) {
  const columns = DAYS.map(
    (day, dayIndex) => `
      <div class="schedule-day" data-schedule-day="${kid.id}:${dayIndex}">
        <div class="schedule-day-head"><strong>${day}</strong></div>
        <div class="schedule-pills" data-schedule-pills="${kid.id}:${dayIndex}"></div>
        <div class="schedule-inline-form" data-schedule-form="${kid.id}:${dayIndex}" hidden>
          <label>Start:<input type="time" data-schedule-start="${kid.id}:${dayIndex}" required /></label>
          <label>End:<input type="time" data-schedule-end="${kid.id}:${dayIndex}" required /></label>
          <div class="schedule-inline-actions">
            <button class="btn-primary" type="button" data-save-schedule="${kid.id}:${dayIndex}">Save</button>
            <button class="btn-secondary" type="button" data-cancel-schedule="${kid.id}:${dayIndex}">Cancel</button>
          </div>
        </div>
        <button class="btn-soft" type="button" data-open-schedule-form="${kid.id}:${dayIndex}">+ Add</button>
      </div>
    `,
  ).join('');

  return `
    <div class="touch-section">
      <h4>Allowed Schedule Windows</h4>
      <div class="schedule-grid-scroll"><div class="schedule-grid">${columns}</div></div>
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
      ${scheduleGrid(kid)}
      ${categoryLimitRows(kid)}
      <div class="avatar-upload-row">
        <input data-avatar-file="${kid.id}" type="file" accept="image/png,image/jpeg,image/webp" />
        <button class="btn-soft" data-upload-avatar="${kid.id}">Upload avatar</button>
        <button class="btn-secondary" data-remove-avatar="${kid.id}">Remove avatar</button>
      </div>
      <div class="inline-form"><input data-pin="${kid.id}" type="password" inputmode="numeric" placeholder="Set PIN" /><button class="btn-soft" data-set-pin="${kid.id}" type="button">Set PIN</button><button class="btn-secondary" data-remove-pin="${kid.id}" type="button">Remove PIN</button></div><button class="btn-primary" data-save="${kid.id}">Save Kid Settings</button>
    </article>
  `;
}

function formatWindowText(start, end) {
  const fmt = (value) => {
    const [h, m] = String(value || '00:00').split(':');
    const d = new Date();
    d.setHours(Number(h || 0), Number(m || 0), 0, 0);
    return d.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
  };
  return `${fmt(start)} – ${fmt(end)}`;
}

function renderSchedules(kidId, schedules) {
  for (let day = 0; day <= 6; day += 1) {
    const daySchedules = schedules
      .filter((item) => Number(item.day_of_week) === day)
      .sort((a, b) => String(a.start_time).localeCompare(String(b.start_time)));
    const pillsEl = body.querySelector(`[data-schedule-pills="${kidId}:${day}"]`);
    if (!pillsEl) continue;
    pillsEl.innerHTML = daySchedules.length
      ? daySchedules
          .map(
            (schedule) => `
              <div class="schedule-pill">
                <span>${formatWindowText(schedule.start_time, schedule.end_time)}</span>
                <button class="btn-link" type="button" data-delete-schedule="${kidId}:${schedule.id}" aria-label="Delete schedule">✕</button>
              </div>
            `,
          )
          .join('')
      : '<span class="small schedule-empty">No windows</span>';
  }
}

async function fillKidExtras(kidId) {
  const [bonus, schedules, categoryLimits] = await Promise.all([
    requestJson(`/api/kids/${kidId}/bonus-time`),
    requestJson(`/api/kids/${kidId}/schedules`),
    requestJson(`/api/kids/${kidId}/category-limits`),
  ]);

  const bonusEl = body.querySelector(`[data-bonus-list="${kidId}"]`);
  bonusEl.textContent = bonus.length
    ? bonus.map((item) => `${item.minutes}m (expires ${formatDate(item.expires_at)})`).join(' • ')
    : 'No active bonus time';

  renderSchedules(kidId, schedules);

  const limitsEl = body.querySelector(`[data-category-limits="${kidId}"]`);
  limitsEl.innerHTML = categoryLimits.length
    ? categoryLimits
        .map(
          (l) => `<div>${l.category_name}: ${l.daily_limit_minutes} min <button class="btn-link" data-delete-category-limit="${kidId}:${l.category_id}" type="button">Delete</button></div>`,
        )
        .join('')
    : 'No per-category overrides.';
}

function closeAllScheduleForms() {
  body.querySelectorAll('[data-schedule-form]').forEach((formEl) => {
    formEl.hidden = true;
  });
  body.querySelectorAll('button[data-open-schedule-form]').forEach((openBtn) => {
    openBtn.hidden = false;
  });
}

function bindScheduleGridEvents() {
  body.querySelectorAll('button[data-open-schedule-form]').forEach((button) => {
    button.addEventListener('click', () => {
      closeAllScheduleForms();
      const key = button.dataset.openScheduleForm;
      const formEl = body.querySelector(`[data-schedule-form="${key}"]`);
      if (!formEl) return;
      formEl.hidden = false;
      button.hidden = true;
    });
  });

  body.querySelectorAll('button[data-cancel-schedule]').forEach((button) => {
    button.addEventListener('click', () => {
      const key = button.dataset.cancelSchedule;
      const formEl = body.querySelector(`[data-schedule-form="${key}"]`);
      const openBtn = body.querySelector(`[data-open-schedule-form="${key}"]`);
      if (formEl) formEl.hidden = true;
      if (openBtn) openBtn.hidden = false;
    });
  });

  body.querySelectorAll('button[data-save-schedule]').forEach((button) => {
    button.addEventListener('click', async () => {
      const [kidIdStr, dayStr] = String(button.dataset.saveSchedule || '').split(':');
      const kidId = Number(kidIdStr);
      const day = Number(dayStr);
      const start = body.querySelector(`[data-schedule-start="${kidId}:${day}"]`)?.value;
      const end = body.querySelector(`[data-schedule-end="${kidId}:${day}"]`)?.value;
      if (!start || !end) {
        showToast('Start and end time are required.', 'error');
        return;
      }

      await requestJson(`/api/kids/${kidId}/schedules`, {
        method: 'POST',
        body: JSON.stringify({ day_of_week: day, start_time: start, end_time: end }),
      });

      await fillKidExtras(kidId);
      bindDeleteEvents();
      bindScheduleGridEvents();
      showToast('Schedule window added.');
    });
  });
}

function bindDeleteEvents() {
  body.querySelectorAll('button[data-delete-schedule]').forEach((button) => {
    button.addEventListener('click', async () => {
      const [kidId, scheduleId] = button.dataset.deleteSchedule.split(':').map(Number);
      await requestJson(`/api/kids/${kidId}/schedules/${scheduleId}`, { method: 'DELETE' });
      const pill = button.closest('.schedule-pill');
      const pillsEl = pill?.parentElement;
      pill?.remove();
      if (pillsEl && !pillsEl.querySelector('.schedule-pill')) {
        pillsEl.innerHTML = '<span class="small schedule-empty">No windows</span>';
      }
    });
  });

  body.querySelectorAll('button[data-delete-category-limit]').forEach((button) => {
    button.addEventListener('click', async () => {
      const [kidId, categoryId] = button.dataset.deleteCategoryLimit.split(':').map(Number);
      await requestJson(`/api/kids/${kidId}/category-limits/${categoryId}`, { method: 'DELETE' });
      await fillKidExtras(kidId);
      bindDeleteEvents();
    });
  });
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

  body.querySelectorAll('button[data-set-pin]').forEach((button) =>
    button.addEventListener('click', async () => {
      const kidId = Number(button.dataset.setPin);
      const pin = body.querySelector(`[data-pin="${kidId}"]`)?.value || '';
      await requestJson(`/api/kids/${kidId}/pin`, { method: 'PUT', body: JSON.stringify({ pin }) });
      showToast('PIN saved.');
    }),
  );

  body.querySelectorAll('button[data-remove-pin]').forEach((button) =>
    button.addEventListener('click', async () => {
      const kidId = Number(button.dataset.removePin);
      await requestJson(`/api/kids/${kidId}/pin`, { method: 'DELETE' });
      showToast('PIN removed.');
    }),
  );

  body.querySelectorAll('button[data-save]').forEach((button) =>
    button.addEventListener('click', async () => {
      const id = Number(button.dataset.save);
      const payload = {
        daily_limit_minutes: Number(body.querySelector(`input[data-limit="${id}"]`)?.value || 0) || null,
        bedtime_start: body.querySelector(`input[data-bedtime-start="${id}"]`)?.value || null,
        bedtime_end: body.querySelector(`input[data-bedtime-end="${id}"]`)?.value || null,
      };
      await requestJson(`/api/kids/${id}`, { method: 'PATCH', body: JSON.stringify(payload) });
      showToast('Kid settings updated.');
    }),
  );

  body.querySelectorAll('button[data-add-bonus]').forEach((button) =>
    button.addEventListener('click', async () => {
      const id = Number(button.dataset.addBonus);
      const minutes = Number(body.querySelector(`input[data-bonus-minutes="${id}"]`)?.value || 0);
      const expiresRaw = body.querySelector(`input[data-bonus-expiry="${id}"]`)?.value;
      await requestJson(`/api/kids/${id}/bonus-time`, {
        method: 'POST',
        body: JSON.stringify({ minutes, expires_at: expiresRaw ? new Date(expiresRaw).toISOString() : null }),
      });
      await fillKidExtras(id);
      bindDeleteEvents();
      showToast('Bonus time added.');
    }),
  );

  body.querySelectorAll('button[data-save-category-limit]').forEach((button) =>
    button.addEventListener('click', async () => {
      const id = Number(button.dataset.saveCategoryLimit);
      const categoryId = Number(body.querySelector(`select[data-limit-category="${id}"]`)?.value);
      const minutes = Number(body.querySelector(`input[data-limit-minutes="${id}"]`)?.value || 0);
      await requestJson(`/api/kids/${id}/category-limits/${categoryId}`, {
        method: 'PUT',
        body: JSON.stringify({ daily_limit_minutes: minutes }),
      });
      await fillKidExtras(id);
      bindDeleteEvents();
      showToast('Category limit saved.');
    }),
  );

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

  body.querySelectorAll('button[data-remove-avatar]').forEach((button) =>
    button.addEventListener('click', async () => {
      const id = Number(button.dataset.removeAvatar);
      await requestJson(`/api/kids/${id}/avatar`, { method: 'DELETE' });
      await loadKids();
    }),
  );

  bindScheduleGridEvents();
  bindDeleteEvents();
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
