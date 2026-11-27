import {createRequire} from 'node:module';
import fs from 'node:fs';

const require = createRequire(import.meta.url);
const path = '../src/modules/pages/static/pages/public_gallery.js';
const state = require(path);
const source = fs.readFileSync(new URL(path, import.meta.url), 'utf8');
const equal = (actual, expected, label) => {
  if (JSON.stringify(actual) !== JSON.stringify(expected)) throw new Error(label);
};

equal(state.nextIndex(0, -1, 4), 3, 'previous-wrap');
equal(state.nextIndex(3, 1, 4), 0, 'next-wrap');
equal(state.nextIndex(2, 0, 4), 2, 'identity');
equal(state.formatCounter(0, 4), ['01', '04'], 'first-counter');
equal(state.formatCounter(31, 32), ['32', '32'], 'last-counter');
for (const args of [[0, 1, 0], [0.5, 1, 2], [0, 1.5, 2]]) {
  let failed = false;
  try { state.nextIndex(...args); } catch (error) { failed = error instanceof TypeError; }
  if (!failed) throw new Error('invalid-state-open');
}
for (const forbidden of [
  'fetch(', 'XMLHttpRequest', 'WebSocket', 'EventSource', 'localStorage',
  'sessionStorage', 'eval(', 'innerHTML', 'insertAdjacentHTML', 'import(',
]) {
  if (source.includes(forbidden)) throw new Error('forbidden:' + forbidden);
}
for (const required of [
  '[data-gallery-dialog]', '[data-gallery-open]', '[data-gallery-photo]',
  '[data-gallery-thumb]', '[data-gallery-prev]', '[data-gallery-next]',
  '[data-gallery-close]', "event.key === 'ArrowLeft'", "event.key === 'ArrowRight'",
  "dialog.addEventListener('cancel'", 'trigger.focus()',
]) {
  if (!source.includes(required)) throw new Error('missing:' + required);
}

console.log(JSON.stringify({schema: 'estakada.rebuild-gallery-viewer-test-v1', status: 'pass', cases: 8}));
