import { test, expect } from '@playwright/test';

const EDITOR_SOURCE = '/source/editor.js';
const ACTIONS = ['p', 'h2', 'h3', 'strong', 'em', 'u', 's', 'ul', 'ol', 'blockquote', 'link', 'unlink'];

function control(name, body) {
  const buttons = ACTIONS.map(action =>
    `<button type="button" data-rich-action="${action}">${action}</button>`).join('');
  return `<section data-rich-control data-control-name="${name}">
    <div role="toolbar">${buttons}</div>
    <div data-rich-editor role="textbox" aria-multiline="true">${body}</div>
    <input type="hidden" name="rich.${name}.changed" value="0" data-rich-changed>
    <textarea hidden disabled name="rich.${name}.value" data-rich-value></textarea>
  </section>`;
}

function fixtureHtml(bodies = ['<p>Text</p>']) {
  return `<!doctype html><html lang="ru"><body>
    <form action="https://never-fetch.invalid/save" method="post" data-editor-form>
      ${bodies.map((body, index) => control(index ? 'body' : 'intro', body)).join('')}
      <p hidden role="alert" data-editor-error-message>safe-error</p>
      <button type="submit" disabled data-editor-save>Save</button>
    </form>
  </body></html>`;
}

async function setFixture(page, bodies = ['<p>Text</p>'], loadScript = true) {
  await page.setContent(fixtureHtml(bodies));
  if (loadScript) await page.addScriptTag({ path: EDITOR_SOURCE });
}

async function selectText(page, controlIndex = 0, start = 0, end = null, selector = 'p') {
  await page.evaluate(({ controlIndex, start, end, selector }) => {
    const editor = document.querySelectorAll('[data-rich-editor]')[controlIndex];
    const node = editor.querySelector(selector)?.firstChild;
    if (!node || node.nodeType !== Node.TEXT_NODE) throw new Error('selection-text-node-missing');
    const range = document.createRange();
    range.setStart(node, start);
    range.setEnd(node, end ?? node.nodeValue.length);
    const selection = window.getSelection();
    selection.removeAllRanges();
    selection.addRange(range);
  }, { controlIndex, start, end, selector });
}

async function observeSubmit(page) {
  await page.evaluate(() => {
    window.__submitObservation = { count: 0, defaultPrevented: null };
    document.querySelector('[data-editor-form]').addEventListener('submit', event => {
      window.__submitObservation.count += 1;
      window.__submitObservation.defaultPrevented = event.defaultPrevented;
      event.preventDefault();
    });
  });
}

async function submission(page) {
  return page.evaluate(() => window.__submitObservation);
}

test('RB4-EDB-001 | init, no-JS and unchanged carrier remain closed', async ({ page, browser }) => {
  await setFixture(page, ['<p>Stable</p>'], false);
  await expect(page.locator('[data-editor-save]')).toBeDisabled();
  expect(await page.locator('[data-rich-editor]').evaluate(node => node.isContentEditable)).toBe(false);

  const noJsContext = await browser.newContext({ javaScriptEnabled: false });
  try {
    const noJsPage = await noJsContext.newPage();
    await noJsPage.setContent(fixtureHtml(['<p>Stable</p>']));
    await expect(noJsPage.locator('[data-editor-save]')).toBeDisabled();
    expect(await noJsPage.locator('[data-rich-editor]').evaluate(node => node.isContentEditable)).toBe(false);
  } finally {
    await noJsContext.close();
  }

  await page.addScriptTag({ path: EDITOR_SOURCE });
  await expect(page.locator('[data-editor-save]')).toBeEnabled();
  expect(await page.locator('[data-rich-editor]').evaluate(node => node.isContentEditable)).toBe(true);
  await observeSubmit(page);
  await page.locator('[data-editor-save]').click();
  expect(await submission(page)).toEqual({ count: 1, defaultPrevented: false });
  await expect(page.locator('[data-rich-changed]')).toHaveValue('0');
  await expect(page.locator('[data-rich-value]')).toBeDisabled();
  await expect(page.locator('[data-rich-value]')).toHaveValue('');
});

test('RB4-EDB-002 | native input and IME dirty only their own control', async ({ page }) => {
  await setFixture(page, ['<p>One</p>', '<p>Two</p>']);
  await page.locator('[data-rich-editor]').first().pressSequentially('X');
  await expect(page.locator('[data-rich-changed]').first()).toHaveValue('1');
  await expect(page.locator('[data-rich-changed]').nth(1)).toHaveValue('0');

  await setFixture(page, ['<p>One</p>', '<p>Two</p>']);
  await page.locator('[data-rich-editor]').nth(1).evaluate(editor => {
    editor.dispatchEvent(new InputEvent('input', {
      bubbles: true, composed: true, inputType: 'insertCompositionText', data: 'Ж', isComposing: true,
    }));
  });
  await expect(page.locator('[data-rich-changed]').first()).toHaveValue('0');
  await expect(page.locator('[data-rich-changed]').nth(1)).toHaveValue('1');
  await observeSubmit(page);
  await page.locator('[data-editor-save]').click();
  await expect(page.locator('[data-rich-value]').first()).toBeDisabled();
  await expect(page.locator('[data-rich-value]').nth(1)).toBeEnabled();
  await expect(page.locator('[data-rich-value]').nth(1)).toHaveValue('<p>Two</p>');
});

test('RB4-EDB-003 | paragraph, line break and paste use the active range', async ({ page }) => {
  await setFixture(page, ['<p>X</p>']);
  await page.locator('[data-rich-editor]').focus();
  await selectText(page, 0, 1, 1);
  await page.keyboard.press('Enter');
  await expect(page.locator('[data-rich-editor]')).toHaveJSProperty('innerHTML', '<p>X</p><p><br></p>');
  await expect(page.locator('[data-rich-changed]')).toHaveValue('1');

  await setFixture(page, ['<p>X</p>']);
  await page.locator('[data-rich-editor]').focus();
  await selectText(page, 0, 1, 1);
  await page.keyboard.press('Shift+Enter');
  await expect(page.locator('[data-rich-editor]')).toHaveJSProperty('innerHTML', '<p>X<br></p>');
  await expect(page.locator('[data-rich-changed]')).toHaveValue('1');

  await setFixture(page, ['<p>X</p>']);
  await selectText(page, 0, 1, 1);
  await page.locator('[data-rich-editor]').evaluate(editor => {
    const data = new DataTransfer();
    data.setData('text/plain', 'A\nB');
    data.setData('text/html', '<img src=x onerror=alert(1)><b>HTML</b>');
    editor.dispatchEvent(new ClipboardEvent('paste', {
      bubbles: true, cancelable: true, clipboardData: data,
    }));
  });
  await expect(page.locator('[data-rich-editor]')).toHaveJSProperty('innerHTML', '<p>XA<br>B</p>');
  await expect(page.locator('[data-rich-editor] img')).toHaveCount(0);
  await expect(page.locator('[data-rich-editor] b')).toHaveCount(0);
  await expect(page.locator('[data-rich-changed]')).toHaveValue('1');

  await setFixture(page, ['<p>X</p>']);
  await page.evaluate(() => {
    const range = document.createRange();
    range.selectNodeContents(document.querySelector('[data-editor-save]'));
    const selection = window.getSelection();
    selection.removeAllRanges();
    selection.addRange(range);
  });
  await page.locator('[data-rich-editor]').evaluate(editor => {
    editor.dispatchEvent(new InputEvent('beforeinput', {
      bubbles: true, cancelable: true, inputType: 'insertParagraph',
    }));
  });
  await expect(page.locator('[data-rich-editor]')).toHaveJSProperty('innerHTML', '<p>X</p>');
  await expect(page.locator('[data-rich-changed]')).toHaveValue('0');
  await page.locator('[data-rich-editor]').evaluate(editor => {
    const data = new DataTransfer();
    data.setData('text/plain', 'outside');
    editor.dispatchEvent(new ClipboardEvent('paste', {
      bubbles: true, cancelable: true, clipboardData: data,
    }));
  });
  await expect(page.locator('[data-rich-editor]')).toHaveJSProperty('innerHTML', '<p>X</p>');
  await expect(page.locator('[data-rich-changed]')).toHaveValue('0');
});

test('RB4-EDB-004 | every literal toolbar mutation marks dirty', async ({ page }) => {
  const expected = {
    strong: '<p><strong>Text</strong></p>', em: '<p><em>Text</em></p>',
    u: '<p><u>Text</u></p>', s: '<p><s>Text</s></p>', p: '<p>Text</p>',
    h2: '<h2>Text</h2>', h3: '<h3>Text</h3>', blockquote: '<blockquote>Text</blockquote>',
    ul: '<ul><li>Text</li></ul>', ol: '<ol><li>Text</li></ol>',
  };
  for (const [action, html] of Object.entries(expected)) {
    await setFixture(page);
    await selectText(page);
    await page.locator(`[data-rich-action="${action}"]`).click();
    await expect(page.locator('[data-rich-editor]')).toHaveJSProperty('innerHTML', html);
    await expect(page.locator('[data-rich-changed]')).toHaveValue('1');
  }
});

test('RB4-EDB-005 | link policy and unlink are browser-enforced without a policy mirror', async ({ page }) => {
  for (const [href, expected] of [
    ['/service/?page=1', '<p><a href="/service/?page=1">Text</a></p>'],
    ['https://example.com/path?page=2', '<p><a href="https://example.com/path?page=2">Text</a></p>'],
  ]) {
    await setFixture(page);
    await selectText(page);
    page.once('dialog', dialog => dialog.accept(href));
    await page.locator('[data-rich-action="link"]').click();
    await expect(page.locator('[data-rich-editor]')).toHaveJSProperty('innerHTML', expected);
    await expect(page.locator('[data-rich-changed]')).toHaveValue('1');
  }

  await setFixture(page, ['<p><a href="/old">Text</a></p>']);
  await selectText(page, 0, 0, 4, 'a');
  await page.locator('[data-rich-action="unlink"]').click();
  await expect(page.locator('[data-rich-editor]')).toHaveJSProperty('innerHTML', '<p>Text</p>');
  await expect(page.locator('[data-rich-changed]')).toHaveValue('1');

  const invalid = [
    'https://user:pass@example.com/path', 'https://example.com:444/path',
    'https://example.com/path#fragment', '/a\\b', '//example.com/path', '/a/../b',
    'http://example.com/path', 'javascript:alert(1)', '/bad%ZZ', '/bad%20space',
    '/bad%00control', '/path?other=1',
  ];
  for (const href of invalid) {
    await setFixture(page);
    await selectText(page);
    page.once('dialog', dialog => dialog.accept(href));
    await page.locator('[data-rich-action="link"]').click();
    await expect(page.locator('[data-editor-error-message]')).toBeVisible();
    await expect(page.locator('[data-rich-changed]')).toHaveValue('0');
    await expect(page.locator('[data-rich-value]')).toBeDisabled();
    await expect(page.locator('[data-rich-editor] a')).toHaveCount(0);
  }
});

test('RB4-EDB-006 | serializer is deterministic for allowed rich content', async ({ page }) => {
  const body = '<p>A &lt; B &amp; C<br><sub>x</sub><sup>2</sup></p>' +
    '<a title="T &quot;Q&quot; &amp;" href="/path?page=2">Link</a>' +
    '<table><caption>Cap</caption><thead><tr>' +
    '<th scope="col" rowspan="2" colspan="3">H</th></tr></thead>' +
    '<tbody><tr><td rowspan="4" colspan="5">D</td></tr></tbody></table>';
  const expected = '<p>A &lt; B &amp; C<br><sub>x</sub><sup>2</sup></p>' +
    '<a href="/path?page=2" title="T &quot;Q&quot; &amp;">Link</a>' +
    '<table><caption>Cap</caption><thead><tr>' +
    '<th colspan="3" rowspan="2" scope="col">H</th></tr></thead>' +
    '<tbody><tr><td colspan="5" rowspan="4">D</td></tr></tbody></table>';
  await setFixture(page, [body]);
  await page.locator('[data-rich-editor]').dispatchEvent('input');
  await observeSubmit(page);
  await page.locator('[data-editor-save]').click();
  expect(await submission(page)).toEqual({ count: 1, defaultPrevented: false });
  await expect(page.locator('[data-rich-value]')).toBeEnabled();
  await expect(page.locator('[data-rich-value]')).toHaveValue(expected);
});

test('RB4-EDB-007 | unsupported DOM fails closed without stripping', async ({ page }) => {
  const invalidBodies = [
    '<div>unsupported</div>', '<p>Text</p><!--comment-->', '<p class="x">attribute</p>',
    '<a href="/bad path">link</a>', '<table><tbody><tr><td colspan="0">cell</td></tr></tbody></table>',
    '<table><thead><tr><th scope="rowgroup">head</th></tr></thead></table>',
  ];
  for (const body of invalidBodies) {
    await setFixture(page, [body]);
    const before = await page.locator('[data-rich-editor]').evaluate(node => node.innerHTML);
    await page.locator('[data-rich-editor]').dispatchEvent('input');
    await observeSubmit(page);
    await page.locator('[data-editor-save]').click();
    expect(await submission(page)).toEqual({ count: 1, defaultPrevented: true });
    await expect(page.locator('[data-rich-value]')).toBeDisabled();
    await expect(page.locator('[data-editor-error-message]')).toBeVisible();
    expect(await page.locator('[data-rich-editor]').evaluate(node => node.innerHTML)).toBe(before);
  }
});

test('RB4-EDB-008 | submit boundary enables only valid serialization and never navigates', async ({ page }) => {
  let requests = 0;
  page.on('request', request => {
    if (request.url().startsWith('https://never-fetch.invalid/')) requests += 1;
  });

  await setFixture(page, ['<p>Exact</p>']);
  await page.locator('[data-rich-editor]').dispatchEvent('input');
  await observeSubmit(page);
  await page.locator('[data-editor-save]').click();
  expect(await submission(page)).toEqual({ count: 1, defaultPrevented: false });
  await expect(page.locator('[data-rich-value]')).toBeEnabled();
  await expect(page.locator('[data-rich-value]')).toHaveValue('<p>Exact</p>');
  expect(requests).toBe(0);

  await setFixture(page, ['<div>Bad</div>']);
  await page.locator('[data-rich-editor]').dispatchEvent('input');
  await observeSubmit(page);
  await page.locator('[data-editor-save]').click();
  expect(await submission(page)).toEqual({ count: 1, defaultPrevented: true });
  await expect(page.locator('[data-rich-value]')).toBeDisabled();
  await expect(page.locator('[data-editor-error-message]')).toBeVisible();
  expect(requests).toBe(0);
});
