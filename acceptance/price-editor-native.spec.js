import { test, expect } from '@playwright/test';

const PRICE_SOURCE = '/source/price-editor.js';
const EDITOR_SOURCE = '/source/editor.js';
const COLUMN_A = '00000000-0000-0000-0000-000000000001';
const COLUMN_B = '00000000-0000-0000-0000-000000000002';
const ROW_A = '00000000-0000-0000-0000-000000000101';
const ROW_B = '00000000-0000-0000-0000-000000000102';

function cell(columnId, kind = '', value = '') {
  return `<div data-price-cell data-price-column-id="${columnId}">
    <label>Тип <select disabled data-price-input data-price-kind>
      <option value=""${kind ? '' : ' selected'}>Нет</option>
      <option value="text"${kind === 'text' ? ' selected' : ''}>Текст</option>
      <option value="amount"${kind === 'amount' ? ' selected' : ''}>Сумма</option>
    </select></label>
    <label data-price-text-fields${kind === 'text' ? '' : ' hidden'}>Текст
      <input disabled maxlength="1000" value="${kind === 'text' ? value : ''}" data-price-input data-price-text>
    </label>
    <span data-price-amount-fields${kind === 'amount' ? '' : ' hidden'}>
      <label>Сумма <input disabled value="${kind === 'amount' ? value : ''}" data-price-input data-price-amount></label>
      <label>От <input disabled type="checkbox" data-price-input data-price-from></label>
    </span>
  </div>`;
}

function column(id, label) {
  return `<div data-price-column data-price-id="${id}">
    <label>Колонка <input disabled required maxlength="500" value="${label}" data-price-input data-price-label></label>
    <button disabled type="button" data-price-input data-price-move="up">←</button>
    <button disabled type="button" data-price-input data-price-move="down">→</button>
    <button disabled type="button" data-price-input data-price-remove>Удалить колонку</button>
  </div>`;
}

function row(id, label, cells) {
  return `<section data-price-row data-price-id="${id}">
    <label>Строка <input disabled required maxlength="500" value="${label}" data-price-input data-price-label></label>
    <button disabled type="button" data-price-input data-price-move="up">↑</button>
    <button disabled type="button" data-price-input data-price-move="down">↓</button>
    <button disabled type="button" data-price-input data-price-remove>Удалить строку</button>
    <div data-price-cells>${cells}</div>
  </section>`;
}

function fixture({ pricesOnly = true } = {}) {
  return `<!doctype html><html><body><form action="https://never-fetch.invalid/save" method="post"
    data-editor-form${pricesOnly ? ' data-prices-only' : ''}>
    <section data-price-control>
      <input type="hidden" name="price.changed" value="0" data-price-changed>
      <div data-price-columns>${column(COLUMN_A, 'Работа')}${column(COLUMN_B, 'Цена')}</div>
      <button disabled type="button" data-price-input data-price-add-column>Добавить колонку</button>
      <div data-price-rows>
        ${row(ROW_A, 'Замена', cell(COLUMN_A, 'text', 'Комплект') + cell(COLUMN_B, 'amount', '100'))}
        ${row(ROW_B, 'Осмотр', cell(COLUMN_A) + cell(COLUMN_B))}
      </div>
      <button disabled type="button" data-price-input data-price-add-row>Добавить строку</button>
      <div data-price-carriers></div>
    </section>
    <p hidden data-editor-error-message>safe-error</p>
    <button type="submit" disabled data-editor-save>Save</button>
  </form></body></html>`;
}

async function setFixture(page, { price = true, editor = true, html = fixture() } = {}) {
  await page.unroute('https://price.test/');
  await page.route('https://price.test/', route => route.fulfill({ contentType: 'text/html', body: html }));
  await page.goto('https://price.test/');
  if (price) await page.addScriptTag({ path: PRICE_SOURCE });
  if (editor) await page.addScriptTag({ path: EDITOR_SOURCE });
}

async function observeSubmit(page) {
  await page.evaluate(() => {
    window.__priceSubmit = null;
    document.querySelector('form').addEventListener('submit', event => {
      window.__priceSubmit = { prevented: event.defaultPrevented, data: [...new FormData(event.currentTarget).entries()] };
      event.preventDefault();
    });
  });
}

test('RB4-EDP-001 | no JS and missing final adapter keep Save disabled', async ({ page, browser }) => {
  const noJs = await browser.newContext({ javaScriptEnabled: false });
  try {
    const noJsPage = await noJs.newPage();
    await noJsPage.setContent(fixture());
    await expect(noJsPage.locator('[data-editor-save]')).toBeDisabled();
    await expect(noJsPage.locator('[data-price-label]').first()).toBeDisabled();
  } finally { await noJs.close(); }

  await setFixture(page, { editor: false });
  await page.locator('[data-price-label]').first().fill('Изменено');
  await expect(page.locator('[data-price-changed]')).toHaveValue('1');
  await expect(page.locator('[data-editor-save]')).toBeDisabled();
});

test('RB4-EDP-002 | both literal readiness markers and dirty state enable prices-only Save', async ({ page }) => {
  await setFixture(page);
  await expect(page.locator('form')).toHaveAttribute('data-price-ready', '1');
  await expect(page.locator('form')).toHaveAttribute('data-editor-ready', '1');
  await expect(page.locator('[data-editor-save]')).toBeDisabled();
  await page.locator('[data-price-label]').first().fill('Новая работа');
  await expect(page.locator('[data-editor-save]')).toBeEnabled();
});

test('RB4-EDP-003 | add and remove column updates every row without orphan cells', async ({ page }) => {
  await setFixture(page);
  await page.locator('[data-price-add-column]').click();
  await expect(page.locator('[data-price-column]')).toHaveCount(3);
  await expect(page.locator('[data-price-row]').first().locator('[data-price-cell]')).toHaveCount(3);
  await expect(page.locator('[data-price-row]').nth(1).locator('[data-price-cell]')).toHaveCount(3);
  await page.locator('[data-price-column]').nth(1).locator('[data-price-remove]').click();
  await expect(page.locator('[data-price-column]')).toHaveCount(2);
  await expect(page.locator(`[data-price-cell][data-price-column-id="${COLUMN_B}"]`)).toHaveCount(0);
});

test('RB4-EDP-004 | add, remove and move rows and columns preserve literal order', async ({ page }) => {
  await setFixture(page);
  await page.locator('[data-price-add-row]').click();
  await expect(page.locator('[data-price-row]')).toHaveCount(3);
  await page.locator('[data-price-row]').nth(2).locator('[data-price-remove]').click();
  await page.locator('[data-price-row]').nth(1).locator('[data-price-move="up"]').click();
  await expect(page.locator('[data-price-row]').first()).toHaveAttribute('data-price-id', ROW_B);
  await page.locator('[data-price-column]').nth(1).locator('[data-price-move="up"]').click();
  await expect(page.locator('[data-price-column]').first()).toHaveAttribute('data-price-id', COLUMN_B);
  await expect(page.locator('[data-price-row]').first().locator('[data-price-cell]').first()).toHaveAttribute('data-price-column-id', COLUMN_B);
});

test('RB4-EDP-005 | absent, text and amount serialize one deterministic fixed wire', async ({ page }) => {
  await setFixture(page);
  const firstCell = page.locator('[data-price-row]').first().locator('[data-price-cell]').first();
  await firstCell.locator('[data-price-kind]').selectOption('amount');
  await firstCell.locator('[data-price-amount]').fill('1250.50');
  await firstCell.locator('[data-price-from]').check();
  await observeSubmit(page);
  await page.locator('[data-editor-save]').click();
  const data = await page.evaluate(() => window.__priceSubmit.data);
  const names = data.map(([name]) => name);
  expect(names.filter(name => name === 'price.column')).toHaveLength(2);
  expect(names.filter(name => name === 'price.row')).toHaveLength(2);
  expect(data.filter(([name]) => name === 'price.cell').map(([, value]) => value)).toEqual([
    `${ROW_A}\t${COLUMN_A}\tamount\t1250.50\t1`,
    `${ROW_A}\t${COLUMN_B}\tamount\t100\t0`,
  ]);
});

test('RB4-EDP-006 | invalid amount and duplicate internal controls fail submit closed', async ({ page }) => {
  await setFixture(page);
  const firstCell = page.locator('[data-price-cell]').first();
  await firstCell.locator('[data-price-kind]').selectOption('amount');
  const amount = firstCell.locator('[data-price-amount]');
  await amount.fill('01');
  await observeSubmit(page);
  await page.locator('[data-editor-save]').click();
  expect(await page.evaluate(() => window.__priceSubmit.prevented)).toBe(true);
  await expect(page.locator('[data-editor-error-message]')).toBeVisible();

  await setFixture(page);
  await page.locator('[data-price-column]').first().evaluate(node => node.append(node.querySelector('[data-price-label]').cloneNode()));
  await page.locator('[data-price-label]').first().fill('Dirty');
  await observeSubmit(page);
  await page.locator('[data-editor-save]').click();
  expect(await page.evaluate(() => window.__priceSubmit.prevented)).toBe(true);
  await expect(page.locator('[data-price-carriers] input')).toHaveCount(0);
});

test('RB4-EDP-007 | insecure context and missing randomUUID have no fallback', async ({ page }) => {
  await page.route('http://insecure.test/', route => route.fulfill({ contentType: 'text/html', body: fixture() }));
  await page.goto('http://insecure.test/');
  await page.addScriptTag({ path: PRICE_SOURCE });
  await page.addScriptTag({ path: EDITOR_SOURCE });
  await expect(page.locator('[data-editor-save]')).toBeDisabled();

  await page.addInitScript(() => Object.defineProperty(window.crypto, 'randomUUID', { value: undefined }));
  await setFixture(page);
  await expect(page.locator('[data-editor-save]')).toBeDisabled();
  await expect(page.locator('form')).not.toHaveAttribute('data-price-ready', '1');
});

test('RB4-EDP-008 | invalid DOM prevents navigation and creates no partial carrier set', async ({ page }) => {
  let requests = 0;
  page.on('request', request => { if (request.url().startsWith('https://never-fetch.invalid/')) requests += 1; });
  await setFixture(page);
  await page.locator('[data-price-cell]').first().evaluate(node => node.append(document.createElement('div')));
  await page.locator('[data-price-label]').first().fill('Dirty');
  await observeSubmit(page);
  await page.locator('[data-editor-save]').click();
  expect(await page.evaluate(() => window.__priceSubmit.prevented)).toBe(true);
  await expect(page.locator('[data-price-carriers] input')).toHaveCount(0);
  expect(requests).toBe(0);
});
