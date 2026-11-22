(() => {
  'use strict';
  const button = document.querySelector('.es-menu-button');
  const menu = document.querySelector('#es-nav');
  if (!button || !menu) return;
  button.addEventListener('click', () => {
    const open = button.getAttribute('aria-expanded') === 'true';
    button.setAttribute('aria-expanded', String(!open));
    menu.dataset.open = String(!open);
  });
})();
