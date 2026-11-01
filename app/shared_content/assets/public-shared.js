/* Trusted menu handler; no editor code, HTML execution or inline CSS. */
(() => {
  'use strict';
  const header = document.querySelector('.es-header');
  if (!header) return;
  const button = header.querySelector('.es-menu-button');
  const nav = header.querySelector('#es-nav');
  if (!button || !nav) return;
  const mobile = matchMedia('(max-width:800px)');
  const setOpen = (open, focusButton = false) => {
    button.setAttribute('aria-expanded', String(open));
    nav.dataset.open = String(open);
    if (focusButton) button.focus();
  };
  setOpen(false);
  header.dataset.menuReady = 'true';
  button.addEventListener('click', event => {
    const open = button.getAttribute('aria-expanded') !== 'true';
    setOpen(open);
    if (open && event.detail === 0) nav.querySelector('a')?.focus();
  });
  header.addEventListener('keydown', event => {
    if (event.key === 'Escape' && button.getAttribute('aria-expanded') === 'true') {
      event.preventDefault();
      setOpen(false, true);
    }
  });
  nav.addEventListener('click', event => {
    if (event.target.closest('a') && mobile.matches) setOpen(false);
  });
  document.addEventListener('click', event => {
    if (!header.contains(event.target)) setOpen(false);
  });
  mobile.addEventListener('change', () => setOpen(false));
})();
