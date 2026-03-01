(function () {
  const stateByContainer = new WeakMap();

  function wait(ms) {
    return new Promise((resolve) => window.setTimeout(resolve, ms));
  }

  function makeThumbUrl(videoId, index) {
    return `https://i.ytimg.com/vi/${videoId}/hq${index}.jpg`;
  }

  async function loadImage(url) {
    const img = new Image();
    img.src = url;
    try {
      await img.decode();
    } catch {
      return null;
    }
    if (!img.naturalWidth || !img.naturalHeight) return null;
    if (img.naturalWidth <= 120 && img.naturalHeight <= 90) return null;
    return img;
  }

  async function getValidPreviewFrames(videoId) {
    const results = [];
    for (let i = 1; i <= 3; i += 1) {
      const url = makeThumbUrl(videoId, i);
      const img = await loadImage(url);
      if (img) results.push(url);
    }
    return results;
  }

  function ensureOverlay(card, thumbClass) {
    const wrap = card.querySelector('.thumbnail-wrap');
    const baseImg = wrap?.querySelector(`img.${thumbClass}`);
    if (!wrap || !baseImg) return null;

    let overlay = wrap.querySelector('img.thumb-preview');
    if (!overlay) {
      overlay = document.createElement('img');
      overlay.className = 'thumb-preview';
      overlay.alt = '';
      wrap.appendChild(overlay);
    }

    let dots = wrap.querySelector('.thumb-dots');
    if (!dots) {
      dots = document.createElement('div');
      dots.className = 'thumb-dots';
      wrap.appendChild(dots);
    }

    return { wrap, overlay, dots };
  }

  function renderDots(dotsEl, count, activeIdx) {
    dotsEl.innerHTML = Array.from({ length: count }, (_, idx) => `<span class="thumb-dot ${idx === activeIdx ? 'active' : ''}"></span>`).join('');
  }

  async function runPreview(card, thumbClass, tabletMode) {
    if (card.dataset.previewRunning === '1') return;
    const link = card.matches('a') ? card : card.querySelector('a[data-video-id]') || card.querySelector('a');
    const videoId = link?.dataset.videoId;
    if (!videoId) return;

    const overlayBits = ensureOverlay(card, thumbClass);
    if (!overlayBits) return;
    const { wrap, overlay, dots } = overlayBits;

    card.dataset.previewRunning = '1';
    wrap.classList.add('previewing');

    try {
      const frames = await getValidPreviewFrames(videoId);
      if (!frames.length) return;
      renderDots(dots, frames.length, 0);
      overlay.src = frames[0];
      overlay.classList.add('visible');

      let idx = 0;
      const maxCycles = tabletMode ? 2 : 4;
      for (let cycle = 0; cycle < maxCycles; cycle += 1) {
        for (let step = 0; step < frames.length; step += 1) {
          if (card.dataset.previewRunning !== '1') return;
          idx = (idx + 1) % frames.length;
          overlay.src = frames[idx];
          renderDots(dots, frames.length, idx);
          await wait(450);
        }
      }
    } finally {
      overlay.classList.remove('visible');
      wrap.classList.remove('previewing');
      card.dataset.previewRunning = '0';
    }
  }

  function stopPreview(card) {
    card.dataset.previewRunning = '0';
    const wrap = card.querySelector('.thumbnail-wrap');
    wrap?.classList.remove('previewing');
    const overlay = wrap?.querySelector('img.thumb-preview');
    overlay?.classList.remove('visible');
  }

  function setupCard(card, thumbClass) {
    if (card.dataset.thumbPreviewBound === '1') return;
    card.dataset.thumbPreviewBound = '1';

    card.addEventListener('mouseenter', () => {
      void runPreview(card, thumbClass, false);
    });
    card.addEventListener('mouseleave', () => {
      stopPreview(card);
    });
  }

  function setupTabletObserver(container, cardSelector, thumbClass) {
    const observer = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          void runPreview(entry.target, thumbClass, true);
        } else {
          stopPreview(entry.target);
        }
      });
    }, { threshold: 0.85 });

    container.querySelectorAll(cardSelector).forEach((card) => observer.observe(card));
    return observer;
  }

  window.initThumbPreview = function initThumbPreview({ containerId, cardSelector, thumbClass }) {
    const container = document.getElementById(containerId);
    if (!container || stateByContainer.has(container)) return;

    const bindCards = () => {
      container.querySelectorAll(cardSelector).forEach((card) => setupCard(card, thumbClass));
    };

    bindCards();

    const mutationObserver = new MutationObserver(() => bindCards());
    mutationObserver.observe(container, { childList: true, subtree: true });

    const tabletObserver = setupTabletObserver(container, cardSelector, thumbClass);
    stateByContainer.set(container, { mutationObserver, tabletObserver });
  };
})();
