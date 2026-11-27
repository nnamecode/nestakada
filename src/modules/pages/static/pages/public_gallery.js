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
    return [String(current + 1).padStart(2, '0'), String(length).padStart(2, '0')];
  }

  if (typeof module === 'object' && module.exports) {
    module.exports = {nextIndex: nextIndex, formatCounter: formatCounter};
  }
  if (!global || !global.document) return;

  var document = global.document;
  var dialog = document.querySelector('[data-gallery-dialog]');
  if (!dialog) return;
  var openers = Array.from(document.querySelectorAll('[data-gallery-open]'));
  var photos = Array.from(dialog.querySelectorAll('[data-gallery-photo]'));
  var thumbs = Array.from(dialog.querySelectorAll('[data-gallery-thumb]'));
  var counter = dialog.querySelector('.es-gallery-counter');
  var closeButton = dialog.querySelector('[data-gallery-close]');
  var previousButton = dialog.querySelector('[data-gallery-prev]');
  var nextButton = dialog.querySelector('[data-gallery-next]');
  var active = 0;
  var trigger = null;
  if (!photos.length || photos.length !== thumbs.length || photos.length !== openers.length
      || !counter || !closeButton || !previousButton || !nextButton) return;

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
    if (trigger) trigger.focus();
  }

  openers.forEach(function (opener, index) {
    opener.addEventListener('click', function () {
      trigger = opener;
      render(index);
      if (typeof dialog.showModal === 'function') dialog.showModal();
      else dialog.setAttribute('open', '');
      closeButton.focus();
    });
  });
  thumbs.forEach(function (thumb, index) {
    thumb.addEventListener('click', function () { render(index); });
  });
  previousButton.addEventListener('click', function () {
    render(nextIndex(active, -1, photos.length));
  });
  nextButton.addEventListener('click', function () {
    render(nextIndex(active, 1, photos.length));
  });
  closeButton.addEventListener('click', closeDialog);
  dialog.addEventListener('click', function (event) {
    if (event.target === dialog) closeDialog();
  });
  dialog.addEventListener('cancel', function (event) {
    event.preventDefault();
    closeDialog();
  });
  dialog.addEventListener('keydown', function (event) {
    if (event.key === 'ArrowLeft') {
      event.preventDefault();
      render(nextIndex(active, -1, photos.length));
    } else if (event.key === 'ArrowRight') {
      event.preventDefault();
      render(nextIndex(active, 1, photos.length));
    }
  });
}(typeof window === 'object' ? window : globalThis));
