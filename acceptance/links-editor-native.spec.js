import { test, expect } from '@playwright/test';

const LINKS_SOURCE = '/source/partner-links-editor.js';
const EDITOR_SOURCE = '/source/editor.js';

function item(label, url) {
  return `<div data-links-item>
    <label>Название <input disabled required value="${label}" data-links-input data-links-label></label>
    <label>HTTPS-адрес <input disabled required value="${url}" data-links-input data-links-url></label>
    <button disabled type="button" data-links-input data-links-move="up">↑</button>
    <button disabled type="button" data-links-input data-links-move="down">↓</button>
    <button disabled type="button" data-links-input data-links-remove>Удалить ссылку</button>
  </div>`;
}

function fixture() {
  return `<!doctype html><html><body><form action="https://never-fetch.invalid/save" method="post" data-editor-form>
    <section data-links-control><h2>Партнёрские ссылки</h2>
      <input type="hidden" name="links.changed" value="0" data-links-changed>
      <div data-links-items>
        ${item('&lt;Первый&gt;', 'https://example.test/one?a=1&amp;b=2')}
        ${item('Второй', 'https://sub.example.test/two')}
      </div>
      <button disabled type="button" data-links-input data-links-add>Добавить ссылку</button>
      <div data-links-carriers></div>
    </section>
    <p hidden data-editor-error-message>safe-error</p>
    <button type="submit" disabled data-editor-save>Save</button>
  </form></body></html>`;
}

async function setFixture(page, { links = true, editor = true, html = fixture() } = {}) {
  await page.unroute('https://links.test/');
  await page.route('https://links.test/', route => route.fulfill({
    contentType: 'text/html; charset=utf-8',
    body: html,
  }));
  await page.goto('https://links.test/');
  if (links) await page.addScriptTag({ path: LINKS_SOURCE });
  if (editor) await page.addScriptTag({ path: EDITOR_SOURCE });
}

async function observeSubmit(page) {
  await page.evaluate(() => {
    window.__linksSubmit = null;
    document.querySelector('form').addEventListener('submit', event => {
      window.__linksSubmit = {
        prevented: event.defaultPrevented,
        data: [...new FormData(event.currentTarget).entries()],
      };
      event.preventDefault();
    });
  });
}

test('RB4-EDLINK-001 | no JS is read-only and missing final adapter keeps Save disabled', async ({ page, browser }) => {
  const noJs = await browser.newContext({ javaScriptEnabled: false });
  try {
    const noJsPage = await noJs.newPage();
    await noJsPage.setContent(fixture());
    await expect(noJsPage.locator('[data-editor-save]')).toBeDisabled();
    await expect(noJsPage.locator('[data-links-label]').first()).toBeDisabled();
  } finally { await noJs.close(); }

  await setFixture(page, { editor: false });
  await expect(page.locator('[data-links-label]').first()).toBeEnabled();
  await expect(page.locator('[data-editor-save]')).toBeDisabled();
});

test('RB4-EDLINK-002 | explicit links and final readiness enable Save with escaped UTF-8 values', async ({ page }) => {
  await setFixture(page);
  await expect(page.locator('form')).toHaveAttribute('data-links-ready', '1');
  await expect(page.locator('form')).toHaveAttribute('data-editor-ready', '1');
  await expect(page.locator('[data-editor-save]')).toBeEnabled();
  await expect(page.locator('[data-links-label]').first()).toHaveValue('<Первый>');
  await expect(page.locator('[data-links-url]').first()).toHaveValue('https://example.test/one?a=1&b=2');
});

test('RB4-EDLINK-003 | add and remove remain bounded to exact64 literal links', async ({ page }) => {
  await setFixture(page);
  for (let index = 0; index < 62; index += 1) await page.locator('[data-links-add]').click();
  await expect(page.locator('[data-links-item]')).toHaveCount(64);
  await expect(page.locator('[data-links-add]')).toBeDisabled();
  await page.locator('[data-links-item]').last().locator('[data-links-remove]').click();
  await expect(page.locator('[data-links-item]')).toHaveCount(63);
  await expect(page.locator('[data-links-add]')).toBeEnabled();
  await expect(page.locator('[data-links-changed]')).toHaveValue('1');
  for (let index = 0; index < 63; index += 1) {
    await page.locator('[data-links-item]').last().locator('[data-links-remove]').click();
  }
  await expect(page.locator('[data-links-item]')).toHaveCount(0);
  await observeSubmit(page);
  await page.locator('[data-editor-save]').click();
  const result = await page.evaluate(() => window.__linksSubmit);
  expect(result.data.filter(([name]) => name === 'links.item')).toHaveLength(0);
  expect(result.data).toContainEqual(['links.changed', '1']);
});

test('RB4-EDLINK-004 | move operations preserve exact visible order', async ({ page }) => {
  await setFixture(page);
  await page.locator('[data-links-item]').nth(1).locator('[data-links-move="up"]').click();
  await expect(page.locator('[data-links-label]').first()).toHaveValue('Второй');
  await page.locator('[data-links-item]').first().locator('[data-links-move="down"]').click();
  await expect(page.locator('[data-links-label]').first()).toHaveValue('<Первый>');
});

test('RB4-EDLINK-005 | changed links serialize fixed wire without client URL-policy mirror', async ({ page }) => {
  await setFixture(page);
  await page.locator('[data-links-url]').nth(1).fill('http://server-must-reject.test/path');
  await observeSubmit(page);
  await page.locator('[data-editor-save]').click();
  const result = await page.evaluate(() => window.__linksSubmit);
  expect(result.prevented).toBe(false);
  expect(result.data.filter(([name]) => name === 'links.item').map(([, value]) => value)).toEqual([
    '<Первый>\thttps://example.test/one?a=1&b=2',
    'Второй\thttp://server-must-reject.test/path',
  ]);
});

test('RB4-EDLINK-006 | unchanged links emit no carriers and cause no navigation', async ({ page }) => {
  let requests = 0;
  page.on('request', request => { if (request.url().startsWith('https://never-fetch.invalid/')) requests += 1; });
  await setFixture(page);
  await observeSubmit(page);
  await page.locator('[data-editor-save]').click();
  const result = await page.evaluate(() => window.__linksSubmit);
  expect(result.data.filter(([name]) => name === 'links.item')).toHaveLength(0);
  expect(result.data).toContainEqual(['links.changed', '0']);
  expect(requests).toBe(0);
});

test('RB4-EDLINK-007 | astral code-point caps pass and invalid plain value fails closed', async ({ page }) => {
  await setFixture(page);
  const astral = '😀';
  await page.locator('[data-links-label]').first().fill(astral.repeat(500));
  await page.locator('[data-links-url]').first().fill(astral.repeat(2048));
  await observeSubmit(page);
  await page.locator('[data-editor-save]').click();
  let result = await page.evaluate(() => window.__linksSubmit);
  expect(result.prevented).toBe(false);
  expect(result.data.filter(([name]) => name === 'links.item')[0][1]).toBe(`${astral.repeat(500)}\t${astral.repeat(2048)}`);

  await setFixture(page);
  await page.locator('[data-links-label]').first().evaluate(input => {
    input.value = 'e\u0301';
    input.dispatchEvent(new InputEvent('input', { bubbles: true, inputType: 'insertText' }));
  });
  await observeSubmit(page);
  await page.locator('[data-editor-save]').click();
  result = await page.evaluate(() => window.__linksSubmit);
  expect(result.prevented).toBe(true);
  await expect(page.locator('[data-editor-error-message]')).toBeVisible();
  await expect(page.locator('[data-links-carriers] input')).toHaveCount(0);
});

test('RB4-EDLINK-008 | swapped direct controls prevent navigation and partial carriers', async ({ page }) => {
  let requests = 0;
  page.on('request', request => { if (request.url().startsWith('https://never-fetch.invalid/')) requests += 1; });
  await setFixture(page);
  await page.locator('[data-links-item]').first().evaluate(node => {
    node.insertBefore(node.children[1], node.children[0]);
  });
  await page.locator('[data-links-label]').first().fill('Dirty');
  await observeSubmit(page);
  await page.locator('[data-editor-save]').click();
  const result = await page.evaluate(() => window.__linksSubmit);
  expect(result.prevented).toBe(true);
  await expect(page.locator('[data-links-carriers] input')).toHaveCount(0);
  expect(requests).toBe(0);
});
