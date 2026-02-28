(function () {
  const body = document.body;
  const kidTiles = Array.from(document.querySelectorAll('[data-kid-id]'));
  const parentControlsLink = document.getElementById('parent-controls-link');

  const pinOverlay = document.getElementById('pin-overlay');
  const pinDots = document.getElementById('pin-dots');
  const pinKeypad = document.getElementById('pin-keypad');
  const pinCancel = document.getElementById('pin-cancel');

  const adminOverlay = document.getElementById('admin-pin-overlay');
  const adminDots = document.getElementById('admin-pin-dots');
  const adminKeypad = document.getElementById('admin-pin-keypad');
  const adminCancel = document.getElementById('admin-pin-cancel');

  let selectedKidId = null;
  let kidDigits = [];
  let adminDigits = [];
  let kidSubmitting = false;
  let adminSubmitting = false;

  async function postJson(url, payload) {
    const response = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });

    let data = {};
    try {
      data = await response.json();
    } catch {
      data = {};
    }

    if (!response.ok) {
      const message = data && data.detail ? data.detail : 'Request failed';
      const error = new Error(message);
      error.status = response.status;
      throw error;
    }

    return data;
  }

  function fadeAndRedirect(path) {
    body.style.opacity = '0';
    window.setTimeout(function () {
      window.location = path;
    }, 400);
  }

  function setOverlayVisible(overlay, isVisible) {
    if (!overlay) return;
    overlay.style.display = isVisible ? 'flex' : 'none';
    overlay.setAttribute('aria-hidden', isVisible ? 'false' : 'true');
  }

  function updateDots(container, length) {
    if (!container) return;
    const dots = container.querySelectorAll('.pin-dot');
    dots.forEach(function (dot, index) {
      dot.classList.toggle('filled', index < length);
    });
  }

  function clearFeedback(container) {
    if (!container) return;
    container.classList.remove('shake');
    container.classList.remove('error');
  }

  function showFailure(container) {
    if (!container) return;
    container.classList.remove('shake');
    container.classList.remove('error');
    void container.offsetWidth;
    container.classList.add('shake');
    container.classList.add('error');
    window.setTimeout(function () {
      container.classList.remove('shake');
      container.classList.remove('error');
    }, 400);
  }

  function clearKidInput() {
    kidDigits = [];
    updateDots(pinDots, kidDigits.length);
    clearFeedback(pinDots);
  }

  function clearAdminInput() {
    adminDigits = [];
    updateDots(adminDots, adminDigits.length);
    clearFeedback(adminDots);
  }

  async function submitKidWithoutPin(kidId) {
    await postJson('/api/session/kid', { kid_id: kidId });
    fadeAndRedirect('/dashboard');
  }

  async function prepareKidPinSession(kidId) {
    const payload = await postJson('/api/session/kid', { kid_id: kidId });
    if (!payload.pin_required) {
      fadeAndRedirect('/dashboard');
      return false;
    }
    return true;
  }

  async function tryKidPinSubmit() {
    if (kidSubmitting || kidDigits.length < 4) return;
    kidSubmitting = true;

    try {
      await postJson('/api/session/kid/verify-pin', { pin: kidDigits.join('') });
      fadeAndRedirect('/dashboard');
    } catch (error) {
      if (error.status === 403) {
        showFailure(pinDots);
        kidDigits = [];
        updateDots(pinDots, kidDigits.length);
      }
    } finally {
      kidSubmitting = false;
    }
  }

  async function tryAdminPinSubmit() {
    if (adminSubmitting || adminDigits.length < 4) return;
    adminSubmitting = true;

    try {
      await postJson('/api/session/admin-verify', { pin: adminDigits.join('') });
      fadeAndRedirect('/admin');
    } catch (error) {
      if (error.status === 403) {
        showFailure(adminDots);
        adminDigits = [];
        updateDots(adminDots, adminDigits.length);
      }
    } finally {
      adminSubmitting = false;
    }
  }

  function handleKeypadPress(event, options) {
    const button = event.target.closest('button');
    if (!button || button.disabled) return;

    if (button.dataset.action === 'backspace') {
      if (options.digits.length > 0) {
        options.digits.pop();
        options.setDigits(options.digits);
        options.update(options.dots, options.digits.length);
      }
      return;
    }

    const key = button.dataset.key;
    if (!key || key < '0' || key > '9') return;

    if (options.digits.length >= 6) return;

    options.digits.push(key);
    options.setDigits(options.digits);
    clearFeedback(options.dots);
    options.update(options.dots, options.digits.length);
    if (options.digits.length >= 4) {
      options.submit();
    }
  }

  kidTiles.forEach(function (tile) {
    tile.addEventListener('click', async function () {
      const kidId = Number(tile.dataset.kidId);
      const hasPin = tile.dataset.hasPin === 'true';

      if (!kidId) return;

      if (hasPin) {
        selectedKidId = kidId;
        clearKidInput();
        try {
          const ready = await prepareKidPinSession(selectedKidId);
          if (!ready) return;
        } catch {
          return;
        }
        setOverlayVisible(pinOverlay, true);
        return;
      }

      try {
        await submitKidWithoutPin(kidId);
      } catch {
        // no-op
      }
    });
  });

  pinKeypad?.addEventListener('click', function (event) {
    handleKeypadPress(event, {
      digits: kidDigits,
      setDigits: function (next) { kidDigits = next.slice(); },
      dots: pinDots,
      update: updateDots,
      submit: tryKidPinSubmit,
    });
  });

  adminKeypad?.addEventListener('click', function (event) {
    handleKeypadPress(event, {
      digits: adminDigits,
      setDigits: function (next) { adminDigits = next.slice(); },
      dots: adminDots,
      update: updateDots,
      submit: tryAdminPinSubmit,
    });
  });

  pinCancel?.addEventListener('click', function () {
    selectedKidId = null;
    clearKidInput();
    setOverlayVisible(pinOverlay, false);
  });

  adminCancel?.addEventListener('click', function () {
    clearAdminInput();
    setOverlayVisible(adminOverlay, false);
  });

  parentControlsLink?.addEventListener('click', function (event) {
    event.preventDefault();
    clearAdminInput();
    setOverlayVisible(adminOverlay, true);
  });

  updateDots(pinDots, 0);
  updateDots(adminDots, 0);

  if (new URLSearchParams(window.location.search).get('admin') === '1') {
    clearAdminInput();
    setOverlayVisible(adminOverlay, true);
  }
})();
