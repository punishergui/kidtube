import { formatDate, requestJson, showToast } from '/static/app.js';

const body = document.getElementById('kids-body');
const form = document.getElementById('add-kid-form');

function row(kid) {
  return `
    <article class="panel admin-card kid-admin-card">
      <div class="admin-card-head">
        <h3>${kid.name}</h3>
        <span class="small">Joined ${formatDate(kid.created_at)}</span>
      </div>
      <div class="kid-admin-meta">
        ${kid.avatar_url ? `<img class="kid-avatar" src="${kid.avatar_url}" alt="${kid.name}" />` : '<span class="kid-avatar kid-initials">★</span>'}
        <label>
          Daily limit minutes
          <input data-limit="${kid.id}" type="number" min="1" value="${kid.daily_limit_minutes || ''}" />
        </label>
      </div>
      <div class="avatar-upload-row">
        <input data-avatar-file="${kid.id}" type="file" accept="image/png,image/jpeg,image/webp" />
        <button class="btn-soft" data-upload-avatar="${kid.id}">Upload avatar</button>
        <button class="btn-secondary" data-remove-avatar="${kid.id}">Remove avatar</button>
      </div>
      <button class="btn-primary" data-save="${kid.id}">Save</button>
    </article>
  `;
}

async function uploadAvatar(kidId) {
  const fileInput = body.querySelector(`input[data-avatar-file="${kidId}"]`);
  const file = fileInput?.files?.[0];
  if (!file) {
    showToast('Choose an image file first.', 'error');
    return;
  }

  const formData = new FormData();
  formData.append('file', file);

  const response = await fetch(`/api/kids/${kidId}/avatar`, {
    method: 'POST',
    body: formData,
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || 'Upload failed');
  }
}

async function removeAvatar(kidId) {
  await requestJson(`/api/kids/${kidId}/avatar`, { method: 'DELETE' });
}

async function loadKids() {
  const kids = await requestJson('/api/kids');

  if (!kids.length) {
    body.innerHTML = '<article class="panel empty-state">No kid profiles yet. Add one above.</article>';
    return;
  }

  body.innerHTML = kids.map(row).join('');

  body.querySelectorAll('button[data-save]').forEach((button) => {
    button.addEventListener('click', async () => {
      const id = Number(button.dataset.save);
      const limitInput = body.querySelector(`input[data-limit="${id}"]`);
      const value = String(limitInput?.value || '').trim();
      const payload = { daily_limit_minutes: value ? Number(value) : null };

      try {
        await requestJson(`/api/kids/${id}`, { method: 'PATCH', body: JSON.stringify(payload) });
        showToast('Kid updated.');
        await loadKids();
      } catch (error) {
        showToast(`Update failed: ${error.message}`, 'error');
      }
    });
  });

  body.querySelectorAll('button[data-upload-avatar]').forEach((button) => {
    button.addEventListener('click', async () => {
      const id = Number(button.dataset.uploadAvatar);
      try {
        await uploadAvatar(id);
        showToast('Avatar uploaded.');
        await loadKids();
      } catch (error) {
        showToast(`Avatar upload failed: ${error.message}`, 'error');
      }
    });
  });

  body.querySelectorAll('button[data-remove-avatar]').forEach((button) => {
    button.addEventListener('click', async () => {
      const id = Number(button.dataset.removeAvatar);
      try {
        await removeAvatar(id);
        showToast('Avatar removed.');
        await loadKids();
      } catch (error) {
        showToast(`Avatar removal failed: ${error.message}`, 'error');
      }
    });
  });
}

form.addEventListener('submit', async (event) => {
  event.preventDefault();
  const data = new FormData(form);
  const limitRaw = String(data.get('daily_limit_minutes') || '').trim();
  const payload = {
    name: String(data.get('name') || '').trim(),
    daily_limit_minutes: limitRaw ? Number(limitRaw) : null,
  };

  try {
    await requestJson('/api/kids', { method: 'POST', body: JSON.stringify(payload) });
    form.reset();
    showToast('Kid created.');
    await loadKids();
  } catch (error) {
    showToast(`Unable to create kid: ${error.message}`, 'error');
  }
});

loadKids().catch((error) => showToast(`Unable to load kids: ${error.message}`, 'error'));
