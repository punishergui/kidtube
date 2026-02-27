import { formatDate, requestJson, showToast } from '/static/app.js';

const body = document.getElementById('kids-body');
const form = document.getElementById('add-kid-form');

function row(kid) {
  return `
    <tr>
      <td>${kid.name}</td>
      <td><input data-limit="${kid.id}" type="number" min="1" value="${kid.daily_limit_minutes || ''}" /></td>
      <td>${kid.avatar_url ? `<img class="avatar" src="${kid.avatar_url}" alt="${kid.name}"/>` : '—'}</td>
      <td>${formatDate(kid.created_at)}</td>
      <td><button data-save="${kid.id}">Save</button></td>
    </tr>
  `;
}

async function loadKids() {
  const kids = await requestJson('/api/kids');
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
}

form.addEventListener('submit', async (event) => {
  event.preventDefault();
  const data = new FormData(form);
  const limitRaw = String(data.get('daily_limit_minutes') || '').trim();
  const payload = {
    name: String(data.get('name') || '').trim(),
    avatar_url: String(data.get('avatar_url') || '').trim() || null,
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
