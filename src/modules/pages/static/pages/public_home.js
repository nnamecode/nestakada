(() => {
  'use strict';
  const root = document.querySelector('[data-home-prices]');
  if (!root) return;
  const tabs = [...root.querySelectorAll('[data-price]')];
  const panels = [...root.querySelectorAll('[data-panel]')];
  const all = root.querySelector('[data-price-all]');
  if (!tabs.length || !panels.length) return;
  tabs.forEach(tab => {
    tab.addEventListener('click', () => {
      tabs.forEach(item => item.setAttribute('aria-pressed', String(item === tab)));
      panels.forEach(panel => { panel.hidden = panel.dataset.panel !== tab.dataset.price; });
      if (all) all.href = tab.dataset.href;
    });
  });
})();
