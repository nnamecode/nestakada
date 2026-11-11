(function (global) {
  'use strict';

  function nextIndex(current, delta, length) {
    if (!Number.isInteger(current) || !Number.isInteger(delta)
        || !Number.isInteger(length) || length < 1) {
      throw new TypeError('PUBLIC_GALLERY_STATE_INVALID');
    }
    return ((current + delta) % length + length) % length;
  }

  function formatCounter(current, length) {
    if (!Number.isInteger(current) || !Number.isInteger(length)
        || current < 0 || current >= length || length < 1) {
      throw new TypeError('PUBLIC_GALLERY_STATE_INVALID');
    }
    return [String(current + 1).padStart(2, '0'),
            String(length).padStart(2, '0')];
  }

  if (typeof module === 'object' && module.exports) {
    module.exports = {nextIndex: nextIndex, formatCounter: formatCounter};
  }
  if (!global || !global.document) return;

  var document = global.document;
  var cards = Array.from(document.querySelectorAll('[data-gallery-modal-url]'));
  cards.forEach(function (card) {
    card.addEventListener('click', function (event) {
      if (event.button !== 0 || event.metaKey || event.ctrlKey
          || event.shiftKey || event.altKey) return;
      var target = card.dataset.galleryModalUrl;
      if (typeof target !== 'string' || !target.startsWith('/gallery-of-works/?')) return;
      event.preventDefault();
      global.location.assign(target);
    });
  });

  var dialog = document.querySelector('[data-gallery-dialog]');
  if (!dialog) return;
  var photos = Array.from(dialog.querySelectorAll('[data-gallery-photo]'));
  var thumbs = Array.from(dialog.querySelectorAll('[data-gallery-thumb]'));
  var counter = dialog.querySelector('.public-gallery-counter');
  var closeLink = dialog.querySelector('.public-gallery-close');
  var active = 0;
  if (!photos.length || photos.length !== thumbs.length || !counter || !closeLink) return;
  var selectedUrl = global.location.pathname + global.location.search;
  var trigger = cards.find(function (card) {
    return card.dataset.galleryModalUrl === selectedUrl;
  }) || null;

  function render(index) {
    active = nextIndex(index, 0, photos.length);
    photos.forEach(function (photo, position) { photo.hidden = position !== active; });
    thumbs.forEach(function (thumb, position) {
      thumb.setAttribute('aria-current', String(position === active));
    });
    var values = formatCounter(active, photos.length);
    counter.replaceChildren();
    var current = document.createElement('b');
    current.textContent = values[0];
    counter.append(current, document.createTextNode(' / ' + values[1]));
    thumbs[active].scrollIntoView({block: 'nearest', inline: 'nearest'});
  }

  function closeDialog() {
    if (dialog.open) dialog.close();
    global.history.replaceState(null, '', closeLink.getAttribute('href'));
    if (trigger) trigger.focus();
  }

  thumbs.forEach(function (thumb, index) {
    thumb.addEventListener('click', function () { render(index); });
  });
  dialog.querySelector('[data-gallery-prev]').addEventListener(
    'click', function () { render(nextIndex(active, -1, photos.length)); });
  dialog.querySelector('[data-gallery-next]').addEventListener(
    'click', function () { render(nextIndex(active, 1, photos.length)); });
  closeLink.addEventListener('click', function (event) {
    event.preventDefault(); closeDialog();
  });
  dialog.addEventListener('click', function (event) {
    if (event.target === dialog) closeDialog();
  });
  dialog.addEventListener('cancel', function (event) {
    event.preventDefault(); closeDialog();
  });
  dialog.addEventListener('keydown', function (event) {
    if (event.key === 'ArrowLeft') {
      event.preventDefault(); render(nextIndex(active, -1, photos.length));
    } else if (event.key === 'ArrowRight') {
      event.preventDefault(); render(nextIndex(active, 1, photos.length));
    }
  });
  render(0);
  if (typeof dialog.showModal === 'function') {
    dialog.removeAttribute('open');
    dialog.showModal();
  }
}(typeof window === 'object' ? window : globalThis));
