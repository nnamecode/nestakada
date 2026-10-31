import { test, expect } from '@playwright/test';
import { route, parseSource } from './migration-source.js';

test.use({ javaScriptEnabled: false, serviceWorkers: 'block' });

test('MIG-SOURCE-001 | source-tool selfcheck, not website AC | pinned own bodies exclude old breadcrumbs and service menus', async ({ page }) => {
  const legacyCanaries = {
    'MAP-003': 'BlackStone', 'MAP-009': 'Уважаемым клиентам', 'MAP-033': 'Установка автозвука',
    'MAP-039': 'Установка многоканальной телефонного', 'MAP-045': 'четырехстоечный подъемник',
    'MAP-078': '27 апреля 2019', 'MAP-090': 'данный раздел сайта находится в разработке',
    'MAP-097': 'с 09-00 до 21-00 мск',
  };
  for (const [id, canary] of Object.entries(legacyCanaries)) {
    const source = await parseSource(page, route(id));
    expect(source.text.includes(canary), `${id}: own legacy canary`).toBe(true);
    expect(source.headings.length, `${id}: own title`).toBe(1);
  }
  for (const id of ['MAP-044', 'MAP-049']) {
    const source = await parseSource(page, route(id));
    expect(source.headings, `${id}: no invented title`).toEqual([]);
    expect(source.text, `${id}: genuinely empty main`).toBe('');
  }
  const services = {};
  for (const id of ['MAP-013', 'MAP-015', 'MAP-032', 'MAP-038', 'MAP-073', 'MAP-088']) {
    const source = await parseSource(page, route(id)); services[id] = source;
    expect(source.headings.length, `${id}: own title`).toBeGreaterThan(0);
    expect(source.text.includes('Все услуги'), `${id}: no bottom menu title`).toBe(false);
    expect(source.text.includes('Другие Услуги'), `${id}: no parent breadcrumb`).toBe(false);
    expect(source.text.includes('>'), `${id}: no breadcrumb separator`).toBe(false);
  }
  const diag = services['MAP-013'];
  expect(diag.tables).toHaveLength(1);
  expect(diag.tables[0][1][0].text).toBe('ВАЗ'); expect(diag.tables[0][1][0].colSpan).toBe(2);
  expect(diag.tables[0][2].map(cell => cell.text)).toEqual(['Диагностика ЭСУД и удаление ошибок', 'от 1500']);
  const polish = services['MAP-038'];
  expect(polish.tables).toHaveLength(1); expect(polish.tables[0]).toHaveLength(6);
  expect(polish.tables[0][1].map(cell => cell.text)).toEqual(['Полировка безабразивная тремя составами', 'от 2500']);
  const climate = services['MAP-073'];
  expect(climate.tables).toHaveLength(1); expect(climate.tables[0]).toHaveLength(3);
  expect(climate.tables[0][2].map(cell => cell.text)).toEqual(['Поиск неисправностей', 'от 3000']);
  // These two sources are inspected but deliberately not compared using a false table-only app oracle.
  expect(services['MAP-015'].tables).toHaveLength(2);
  expect(services['MAP-032'].tables).toHaveLength(0);
  expect(services['MAP-032'].text.includes('1900'), 'MAP-032: non-table price exists').toBe(true);
  const wash = services['MAP-088'];
  expect(wash.headings).toEqual(['Автомойка']); expect(wash.tables).toHaveLength(1);
  expect(wash.tables[0][1].map(cell => cell.text)).toEqual(['Техническая мойка', '300', '300', '400', '400', '500', '600']);
  expect(wash.proseText).toBe('');
});
