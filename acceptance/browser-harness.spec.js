import { test, expect } from '@playwright/test';
import { parseMetadata } from './html-metadata.js';

test.use({ javaScriptEnabled: false, serviceWorkers: 'block' });

test('HARNESS-005 | browser starts and assertions work on synthetic in-memory HTML', async ({ page }) => {
  await page.route('**/*', route => route.abort());
  await page.setContent('<!doctype html><html lang="ru"><title>Проверка инструмента</title><body><h1>Синтетический тест</h1><button type="button">Проверить</button></body></html>');
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Синтетический тест');
  await page.getByRole('button', { name: 'Проверить', exact: true }).click();
  await expect(page).toHaveTitle('Проверка инструмента');
});

test('HARNESS-007 | metadata parser is inert and works with page JS disabled', async ({ page }) => {
  const html = '<!doctype html><html><head>' +
    '<link rel="canonical" href="http://127.0.0.1:8000/example">' +
    '<meta name="viewport" content="width=device-width, initial-scale=1">' +
    '<meta http-equiv="refresh" content="0;url=https://never-fetch.invalid/">' +
    '<script>globalThis.__acceptanceExecuted = true</script>' +
    '</head><body><img src="https://never-fetch.invalid/a.png" onerror="globalThis.__acceptanceExecuted = true"></body></html>';
  const metadata = await parseMetadata(page, html);
  expect(metadata.canonical).toEqual([{ href: 'http://127.0.0.1:8000/example', inHead: true }]);
  expect(metadata.viewport).toEqual([{ content: 'width=device-width, initial-scale=1', inHead: true }]);
  expect(metadata.refreshCount).toBe(1);
  expect(page.url()).toBe('about:blank');
  expect(await page.evaluate(() => globalThis.__acceptanceExecuted)).toBeUndefined();
});
