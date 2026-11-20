import { test, expect } from '@playwright/test';

const ACTION_SOURCE = '/source/action-copy-editor.js';
const EDITOR_SOURCE = '/source/editor.js';
const ACTIONS = ['p', 'h2', 'h3', 'strong', 'em', 'u', 's', 'ul', 'ol', 'blockquote', 'link', 'unlink'];

function bodyControl(index, body) {
  const buttons = ACTIONS.map(action =>
    `<button type="button" data-rich-action="${action}">${action}</button>`).join('');
  return `<section data-rich-control data-action-body>
    <h3>Описание</h3><div role="toolbar">${buttons}</div>
    <div data-rich-editor role="textbox" aria-multiline="true">${body}</div>
    <input type="hidden" name="actions.${index}.body.changed" value="0" data-rich-changed>
    <textarea hidden disabled name="actions.${index}.body.value" data-rich-value></textarea>
  </section>`;
}

function card(index, title, body, url) {
  return `<section data-action-card data-action-index="${index}">
    <label>Название<input disabled required type="text" name="actions.${index}.title" value="${title}" data-action-title></label>
    <p>Переход: <code data-action-url>${url}</code></p>
    ${bodyControl(index, body)}
  </section>`;
}

function fixture(cards = [
  card(0, '&lt;Первая&gt;', '<p>Один &amp; два</p>', '/one/?page=1&amp;view=full'),
  card(1, 'Вторая', '<p>Текст</p>', '/two/'),
]) {
  return `<!doctype html><html lang="ru"><body>
    <form action="https://never-fetch.invalid/save" method="post" data-editor-form>
      <section data-actions-control><h2>Акции</h2><div data-action-cards>${cards.join('')}</div></section>
      <p hidden role="alert" data-editor-error-message>safe-error</p>
      <button type="submit" disabled data-editor-save>Save</button>
    </form>
  </body></html>`;
}

async function setFixture(page, { html = fixture(), action = true, editor = true } = {}) {
  await page.setContent(html);
  if (action) await page.addScriptTag({ path: ACTION_SOURCE });
  if (editor) await page.addScriptTag({ path: EDITOR_SOURCE });
}

async function observeSubmit(page) {
  await page.evaluate(() => {
    window.__actionSubmit = null;
    document.querySelector('form').addEventListener('submit', event => {
      window.__actionSubmit = {
        prevented: event.defaultPrevented,
        data: [...new FormData(event.currentTarget).entries()],
      };
      event.preventDefault();
    });
  });
}

test('RB4-EDACTION-001 | no JS is read-only and missing final adapter keeps Save disabled', async ({ page, browser }) => {
  const noJs = await browser.newContext({ javaScriptEnabled: false });
  try {
    const noJsPage = await noJs.newPage();
    await noJsPage.setContent(fixture());
    await expect(noJsPage.locator('[data-editor-save]')).toBeDisabled();
    await expect(noJsPage.locator('[data-action-title]').first()).toBeDisabled();
    expect(await noJsPage.locator('[data-rich-editor]').first().evaluate(node => node.isContentEditable)).toBe(false);
  } finally { await noJs.close(); }

  await setFixture(page, { editor: false });
  await expect(page.locator('[data-action-title]').first()).toBeEnabled();
  await expect(page.locator('[data-editor-save]')).toBeDisabled();
});

test('RB4-EDACTION-002 | fixed cards become ready with escaped UTF-8 and read-only URLs', async ({ page }) => {
  await setFixture(page);
  await expect(page.locator('form')).toHaveAttribute('data-actions-ready', '1');
  await expect(page.locator('form')).toHaveAttribute('data-editor-ready', '1');
  await expect(page.locator('[data-editor-save]')).toBeEnabled();
  await expect(page.locator('[data-action-title]').first()).toHaveValue('<Первая>');
  await expect(page.locator('[data-action-url]').first()).toHaveText('/one/?page=1&view=full');
  await expect(page.locator('[data-action-url]')).toHaveCount(2);
  await expect(page.locator('[data-action-url] input, [data-action-url] button')).toHaveCount(0);
});

test('RB4-EDACTION-003 | title submits natively while unchanged bodies emit no values', async ({ page }) => {
  await setFixture(page);
  await page.locator('[data-action-title]').first().fill('Новое название');
  await observeSubmit(page);
  await page.locator('[data-editor-save]').click();
  const result = await page.evaluate(() => window.__actionSubmit);
  expect(result.prevented).toBe(false);
  expect(result.data).toContainEqual(['actions.0.title', 'Новое название']);
  expect(result.data.filter(([name]) => name.endsWith('.body.value'))).toHaveLength(0);
  expect(result.data.filter(([name]) => name.endsWith('.body.changed')).map(([, value]) => value)).toEqual(['0', '0']);
});

test('RB4-EDACTION-004 | changed rich body serializes through the shared editor', async ({ page }) => {
  await setFixture(page);
  await page.locator('[data-rich-editor]').first().evaluate(editor => {
    editor.innerHTML = '<p><strong>Новый текст</strong></p>';
    editor.dispatchEvent(new InputEvent('input', { bubbles: true, inputType: 'insertText' }));
  });
  await observeSubmit(page);
  await page.locator('[data-editor-save]').click();
  const result = await page.evaluate(() => window.__actionSubmit);
  expect(result.prevented).toBe(false);
  expect(result.data).toContainEqual(['actions.0.body.changed', '1']);
  expect(result.data).toContainEqual(['actions.0.body.value', '<p><strong>Новый текст</strong></p>']);
  expect(result.data).toContainEqual(['actions.1.body.changed', '0']);
});

test('RB4-EDACTION-005 | two bodies retain independent flags and fixed order', async ({ page }) => {
  await setFixture(page);
  await page.locator('[data-rich-editor]').nth(1).dispatchEvent('input');
  await observeSubmit(page);
  await page.locator('[data-editor-save]').click();
  const result = await page.evaluate(() => window.__actionSubmit);
  expect(result.data.filter(([name]) => name.endsWith('.body.changed'))).toEqual([
    ['actions.0.body.changed', '0'], ['actions.1.body.changed', '1'],
  ]);
  expect(result.data.filter(([name]) => name.endsWith('.title')).map(([name]) => name)).toEqual([
    'actions.0.title', 'actions.1.title',
  ]);
});

test('RB4-EDACTION-006 | unsupported rich DOM fails closed without partial value', async ({ page }) => {
  await setFixture(page);
  await page.locator('[data-rich-editor]').first().evaluate(editor => {
    editor.innerHTML = '<div>Unsupported</div>';
    editor.dispatchEvent(new InputEvent('input', { bubbles: true, inputType: 'insertText' }));
  });
  await observeSubmit(page);
  await page.locator('[data-editor-save]').click();
  const result = await page.evaluate(() => window.__actionSubmit);
  expect(result.prevented).toBe(true);
  await expect(page.locator('[data-editor-error-message]')).toBeVisible();
  await expect(page.locator('[data-rich-value]').first()).toBeDisabled();
});

test('RB4-EDACTION-007 | zero cards are ready and structural controls do not exist', async ({ page }) => {
  await setFixture(page, { html: fixture([]) });
  await expect(page.locator('form')).toHaveAttribute('data-actions-ready', '1');
  await expect(page.locator('[data-editor-save]')).toBeEnabled();
  await expect(page.locator('[data-action-card]')).toHaveCount(0);
  await expect(page.locator('[data-actions-control] button')).toHaveCount(0);
  await observeSubmit(page);
  await page.locator('[data-editor-save]').click();
  const result = await page.evaluate(() => window.__actionSubmit);
  expect(result.data.filter(([name]) => name.startsWith('actions.'))).toHaveLength(0);
});

test('RB4-EDACTION-008 | swapped fixed shape stays closed without navigation', async ({ page }) => {
  let requests = 0;
  page.on('request', request => { if (request.url().startsWith('https://never-fetch.invalid/')) requests += 1; });
  await page.setContent(fixture());
  await page.locator('[data-action-card]').nth(1).evaluate(cardNode => {
    cardNode.insertBefore(cardNode.children[1], cardNode.children[0]);
  });
  await page.addScriptTag({ path: ACTION_SOURCE });
  await page.addScriptTag({ path: EDITOR_SOURCE });
  await expect(page.locator('form')).toHaveAttribute('data-editor-error', '1');
  await expect(page.locator('[data-editor-save]')).toBeDisabled();
  await expect(page.locator('[data-action-title]')).toHaveCount(2);
  await expect(page.locator('[data-action-title]').first()).toBeDisabled();
  await expect(page.locator('[data-action-title]').nth(1)).toBeDisabled();
  await expect(page.locator('form')).not.toHaveAttribute('data-actions-ready', '1');
  expect(requests).toBe(0);
});
