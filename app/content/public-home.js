(() => {
  'use strict';
  const root = document.querySelector('[data-home-prices]');
  if (!root) return;
  const tabs = [...root.querySelectorAll('[data-home-price-tab]')];
  const panels = [...root.querySelectorAll('[data-home-price-panel]')];
  if (!tabs.length || tabs.length !== panels.length) return;
  const tablist = root.querySelector('[data-home-price-tabs]');
  if (!tablist) return;
  tablist.setAttribute('role', 'tablist');
  const select = index => {
    tabs.forEach((tab, current) => {
      const selected = current === index;
      tab.setAttribute('aria-selected', selected ? 'true' : 'false');
      tab.tabIndex = selected ? 0 : -1;
      panels[current].hidden = !selected;
    });
  };
  root.setAttribute('data-home-enhanced', 'true');
  tabs.forEach((tab, index) => {
    tab.setAttribute('role', 'tab');
    tab.id = `home-price-tab-${index + 1}`;
    tab.setAttribute('aria-controls', panels[index].id);
    panels[index].setAttribute('role', 'tabpanel');
    panels[index].setAttribute('aria-labelledby', tab.id);
    tab.addEventListener('click', event => {
      event.preventDefault();
      select(index);
    });
    tab.addEventListener('keydown', event => {
      if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
      event.preventDefault();
      const next = event.key === 'Home' ? 0 : event.key === 'End' ? tabs.length - 1
        : (index + (event.key === 'ArrowRight' ? 1 : -1) + tabs.length) % tabs.length;
      select(next);
      tabs[next].focus();
    });
  });
  select(0);
})();
