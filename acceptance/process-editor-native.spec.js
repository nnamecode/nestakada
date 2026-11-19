import { test, expect } from '@playwright/test';

const PROCESS_SOURCE = '/source/process-steps-editor.js';
const EDITOR_SOURCE = '/source/editor.js';

function step(title, body) {
  return `<div data-process-step>
    <label>Название <input disabled required value="${title}" data-process-input data-process-title></label>
    <label>Описание <input disabled value="${body}" data-process-input data-process-body></label>
    <button disabled type="button" data-process-input data-process-move="up">↑</button>
    <button disabled type="button" data-process-input data-process-move="down">↓</button>
    <button disabled type="button" data-process-input data-process-remove>Удалить этап</button>
  </div>`;
}

function fixture() {
  return `<!doctype html><html><body><form action="https://never-fetch.invalid/save" method="post" data-editor-form>
    <section data-rich-control><h2>Lead</h2>
      <div data-rich-editor role="textbox"><p>Lead</p></div>
      <input type="hidden" name="rich.lead.changed" value="0" data-rich-changed>
      <textarea hidden disabled name="rich.lead.value" data-rich-value></textarea>
    </section>
    <section data-process-control><h2>Этапы работы</h2>
      <input type="hidden" name="process.changed" value="0" data-process-changed>
      <div data-process-steps>${step('&lt;Приём&gt;', 'A &gt; B')}${step('Ремонт', '')}</div>
      <button disabled type="button" data-process-input data-process-add>Добавить этап</button>
      <div data-process-carriers></div>
    </section>
    <p hidden data-editor-error-message>safe-error</p>
    <button type="submit" disabled data-editor-save>Save</button>
  </form></body></html>`;
}

async function setFixture(page, { process = true, editor = true, html = fixture() } = {}) {
  await page.unroute('https://process.test/');
  await page.route('https://process.test/', route => route.fulfill({ contentType: 'text/html; charset=utf-8', body: html }));
  await page.goto('https://process.test/');
  if (process) await page.addScriptTag({ path: PROCESS_SOURCE });
  if (editor) await page.addScriptTag({ path: EDITOR_SOURCE });
}

async function observeSubmit(page) {
  await page.evaluate(() => {
    window.__processSubmit = null;
    document.querySelector('form').addEventListener('submit', event => {
      window.__processSubmit = {
        prevented: event.defaultPrevented,
        data: [...new FormData(event.currentTarget).entries()],
      };
      event.preventDefault();
    });
  });
}

test('RB4-EDPROC-001 | no JS is read-only and missing final adapter keeps Save disabled', async ({ page, browser }) => {
  const noJs = await browser.newContext({ javaScriptEnabled: false });
  try {
    const noJsPage = await noJs.newPage();
    await noJsPage.setContent(fixture());
    await expect(noJsPage.locator('[data-editor-save]')).toBeDisabled();
    await expect(noJsPage.locator('[data-process-title]').first()).toBeDisabled();
  } finally { await noJs.close(); }

  await setFixture(page, { editor: false });
  await expect(page.locator('[data-process-title]').first()).toBeEnabled();
  await expect(page.locator('[data-editor-save]')).toBeDisabled();
});

test('RB4-EDPROC-002 | explicit process and final readiness enable Save with escaped literal values', async ({ page }) => {
  await setFixture(page);
  await expect(page.locator('form')).toHaveAttribute('data-process-ready', '1');
  await expect(page.locator('form')).toHaveAttribute('data-editor-ready', '1');
  await expect(page.locator('[data-editor-save]')).toBeEnabled();
  await expect(page.locator('[data-process-title]').first()).toHaveValue('<Приём>');
  await expect(page.locator('[data-process-body]').first()).toHaveValue('A > B');
});

test('RB4-EDPROC-003 | add and remove remain bounded to exact12 literal steps', async ({ page }) => {
  await setFixture(page);
  for (let index = 0; index < 10; index += 1) await page.locator('[data-process-add]').click();
  await expect(page.locator('[data-process-step]')).toHaveCount(12);
  await expect(page.locator('[data-process-add]')).toBeDisabled();
  await page.locator('[data-process-step]').last().locator('[data-process-remove]').click();
  await expect(page.locator('[data-process-step]')).toHaveCount(11);
  await expect(page.locator('[data-process-add]')).toBeEnabled();
  await expect(page.locator('[data-process-changed]')).toHaveValue('1');
});

test('RB4-EDPROC-004 | move operations preserve the exact visible order', async ({ page }) => {
  await setFixture(page);
  await page.locator('[data-process-step]').nth(1).locator('[data-process-move="up"]').click();
  await expect(page.locator('[data-process-title]').first()).toHaveValue('Ремонт');
  await page.locator('[data-process-step]').first().locator('[data-process-move="down"]').click();
  await expect(page.locator('[data-process-title]').first()).toHaveValue('<Приём>');
});

test('RB4-EDPROC-005 | changed steps serialize one fixed repeated wire in display order', async ({ page }) => {
  await setFixture(page);
  await page.locator('[data-process-body]').nth(1).fill('Готово');
  await observeSubmit(page);
  await page.locator('[data-editor-save]').click();
  const result = await page.evaluate(() => window.__processSubmit);
  expect(result.prevented).toBe(false);
  expect(result.data.filter(([name]) => name === 'process.step').map(([, value]) => value)).toEqual([
    '<Приём>\tA > B',
    'Ремонт\tГотово',
  ]);
});

test('RB4-EDPROC-006 | unchanged process emits no step carriers', async ({ page }) => {
  await setFixture(page);
  await observeSubmit(page);
  await page.locator('[data-editor-save]').click();
  const result = await page.evaluate(() => window.__processSubmit);
  expect(result.data.filter(([name]) => name === 'process.step')).toHaveLength(0);
  expect(result.data).toContainEqual(['process.changed', '0']);
});

test('RB4-EDPROC-007 | astral code-point caps pass and invalid plain value fails closed', async ({ page }) => {
  await setFixture(page);
  const astral = '😀';
  await page.locator('[data-process-title]').first().fill(astral.repeat(500));
  await page.locator('[data-process-body]').first().fill(astral.repeat(4000));
  await observeSubmit(page);
  await page.locator('[data-editor-save]').click();
  let result = await page.evaluate(() => window.__processSubmit);
  expect(result.prevented).toBe(false);
  expect(result.data.filter(([name]) => name === 'process.step')[0][1]).toBe(`${astral.repeat(500)}\t${astral.repeat(4000)}`);

  await setFixture(page);
  await page.locator('[data-process-title]').first().evaluate(input => {
    input.value = 'e\u0301';
    input.dispatchEvent(new InputEvent('input', { bubbles: true, inputType: 'insertText' }));
  });
  await observeSubmit(page);
  await page.locator('[data-editor-save]').click();
  result = await page.evaluate(() => window.__processSubmit);
  expect(result.prevented).toBe(true);
  await expect(page.locator('[data-editor-error-message]')).toBeVisible();
  await expect(page.locator('[data-process-carriers] input')).toHaveCount(0);
});

test('RB4-EDPROC-008 | malformed DOM prevents navigation and creates no carrier set', async ({ page }) => {
  let requests = 0;
  page.on('request', request => { if (request.url().startsWith('https://never-fetch.invalid/')) requests += 1; });
  await setFixture(page);
  await page.locator('[data-process-step]').first().evaluate(node => {
    node.insertBefore(node.children[1], node.children[0]);
  });
  await page.locator('[data-process-title]').first().fill('Dirty');
  await observeSubmit(page);
  await page.locator('[data-editor-save]').click();
  const result = await page.evaluate(() => window.__processSubmit);
  expect(result.prevented).toBe(true);
  await expect(page.locator('[data-process-carriers] input')).toHaveCount(0);
  expect(requests).toBe(0);
});
