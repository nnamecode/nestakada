(() => {
  'use strict';
  const priceRoot = document.querySelector('[data-home-prices]');
  if (priceRoot) {
    const tabs = [...priceRoot.querySelectorAll('[data-price]')];
    const panels = [...priceRoot.querySelectorAll('[data-panel]')];
    const all = priceRoot.querySelector('[data-price-all]');
    tabs.forEach(tab => {
      tab.addEventListener('click', () => {
        tabs.forEach(item => item.setAttribute('aria-pressed', String(item === tab)));
        panels.forEach(panel => { panel.hidden = panel.dataset.panel !== tab.dataset.price; });
        if (all) all.href = tab.dataset.href;
      });
    });
  }

  const strip = document.querySelector('#estakada-public-v4 .es-photo-strip');
  const image = strip?.querySelector('.es-photo-strip-image');
  const syncPhotoStrip = () => {
    if (!strip || !image) return;
    if (window.innerWidth <= 800) {
      strip.style.removeProperty('background-image');
      return;
    }
    const source = image.currentSrc || image.src;
    strip.style.setProperty('background-image', `url(${JSON.stringify(source)})`, 'important');
  };

  window.addEventListener('resize', syncPhotoStrip);
  syncPhotoStrip();
})();
