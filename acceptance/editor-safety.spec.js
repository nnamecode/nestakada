import { test as base, expect } from '@playwright/test';
import { openApplicationDriver } from './application-driver-contract.js';

const test = base.extend({ app: async ({}, use) => {
  const app = await openApplicationDriver();
  try { await use(app); } finally { await app.close(); }
} });
test.use({ javaScriptEnabled: false, serviceWorkers: 'block' });

const safeHtml = '<h2>EDITOR-SAFE-HEADING</h2><p>EDITOR-SAFE-PARAGRAPH <strong>важно</strong> <em>пояснение</em></p>' +
  '<ul><li>EDITOR-SAFE-LIST</li></ul><table><caption>EDITOR-SAFE-TABLE</caption>' +
  '<thead><tr><th scope="col">Элемент</th><th scope="col">Описание</th></tr></thead>' +
  '<tbody><tr><td>EDITOR-SAFE-CELL</td><td>Текст без цены</td></tr></tbody></table>';
const fields = ['id', 'url', 'parentId', 'published', 'h1', 'title', 'description', 'assetId',
  'price', 'publicText', 'draftText', 'revision', 'versions', 'currentVersionId'];
function unchanged(after, before) {
  for (const field of fields) {
    expect(before).toHaveProperty(field); expect(after).toHaveProperty(field);
    expect(after[field], field).toEqual(before[field]);
  }
}
async function parse(page, html) {
  expect(typeof html).toBe('string');
  return page.evaluate(source => {
    const doc = new DOMParser().parseFromString(source, 'text/html');
    const clean = value => value.replace(/\s+/gu, ' ').trim();
    return {
      text: clean(doc.body.textContent),
      h2: [...doc.querySelectorAll('h2')].map(node => clean(node.textContent)),
      strong: [...doc.querySelectorAll('strong')].map(node => clean(node.textContent)),
      emphasis: [...doc.querySelectorAll('em')].map(node => clean(node.textContent)),
      items: [...doc.querySelectorAll('li')].map(node => clean(node.textContent)),
      captions: [...doc.querySelectorAll('caption')].map(node => clean(node.textContent)),
      cells: [...doc.querySelectorAll('th,td')].map(node => clean(node.textContent)),
      links: [...doc.querySelectorAll('a')].map(node => ({
        text: clean(node.textContent), href: node.getAttribute('href'), target: node.getAttribute('target'),
        rel: (node.getAttribute('rel') ?? '').split(/\s+/u).filter(Boolean),
      })),
    };
  }, html);
}
test.beforeEach(async ({ page }) => {
  await page.route('**/*', request => request.abort());
  await page.routeWebSocket('**/*', socket => socket.close());
});
async function currentHtml(app) {
  const page = await app.observe('page', { page: 'P-ASSIGNED' });
  const stored = await app.observe('page-rich-text-html', { page: 'P-ASSIGNED' });
  expect(stored.pageId).toBe(page.id); expect(stored.revision).toBe(page.revision);
  expect(stored.versionId).toBe(page.currentVersionId);
  expect(typeof stored.html).toBe('string'); expect(typeof stored.versionHtml).toBe('string');
  const published = await app.observe('public-rich-text-html', { page: 'P-ASSIGNED' });
  expect(published.status).toBe(200); expect(published.pageId).toBe(page.id);
  expect(typeof published.html).toBe('string');
  return { page, stored, published };
}
async function publish(app, actor, html, revision) {
  return app.act(actor, 'publish-rich-text-direct', { page: 'P-ASSIGNED', base: revision, html });
}
function safeStructure(actual) {
  expect(actual.h2).toContain('EDITOR-SAFE-HEADING');
  expect(actual.text).toContain('EDITOR-SAFE-PARAGRAPH');
  expect(actual.strong).toContain('важно'); expect(actual.emphasis).toContain('пояснение');
  expect(actual.items).toContain('EDITOR-SAFE-LIST');
  expect(actual.captions).toContain('EDITOR-SAFE-TABLE');
  expect(actual.cells).toEqual(['Элемент', 'Описание', 'EDITOR-SAFE-CELL', 'Текст без цены']);
}
async function positiveControl(app, page, actor, before) {
  expect((await publish(app, actor, safeHtml, before.revision)).outcome).toBe('accepted');
  const after = await currentHtml(app);
  expect(after.page.versions).toHaveLength(before.versions.length + 1);
  for (const html of [after.stored.html, after.stored.versionHtml, after.published.html]) safeStructure(await parse(page, html));
}

test('EDITOR-SAFE-104-allowed | AT-104 AC-DTL-004 | allowed headings, emphasis, list and non-price table survive publication and versioning', async ({ app, page }) => {
  await app.reset('assigned-page-with-owner-draft');
  const before = await app.observe('page', { page: 'P-ASSIGNED' });
  await positiveControl(app, page, 'S-EDIT', before);
  const after = await app.observe('page', { page: 'P-ASSIGNED' });
  for (const field of ['url', 'h1', 'title', 'description', 'price', 'assetId', 'draftText']) expect(after[field]).toEqual(before[field]);
});

const activeMarkup = [
  ['event', '<p onclick="window.EDITOR_EXECUTION_CANARY=1">EDITOR-REJECT-CANARY</p>'],
  ['script', '<p>EDITOR-REJECT-CANARY</p><script>window.EDITOR_EXECUTION_CANARY=1</script>'],
  ['iframe', '<p>EDITOR-REJECT-CANARY</p><iframe src="https://example.invalid/editor-probe"></iframe>'],
  ['css-url', '<p style="background-image:url(https://example.invalid/editor-probe)">EDITOR-REJECT-CANARY</p>'],
  ['css-position', '<p style="position:fixed;z-index:999">EDITOR-REJECT-CANARY</p>'],
  ['template-expression', '<p>EDITOR-REJECT-CANARY {{ request.user }}</p>'],
  ['template-tag', '<p>EDITOR-REJECT-CANARY {% include "synthetic.html" %}</p>'],
  ['template-comment', '<p>EDITOR-REJECT-CANARY {# synthetic #}</p>'],
];
for (const actor of ['OWNER', 'S-EDIT']) {
  for (const [id, html] of activeMarkup) {
    test(`EDITOR-SAFE-104-${actor}-${id} | AT-104 AC-DTL-004 | active markup is refused without publishing a sanitized remainder`, async ({ app, page }) => {
      await app.reset('assigned-page-with-owner-draft');
      const before = await currentHtml(app);
      const result = await publish(app, actor, html, before.page.revision);
      expect(result.outcome).toBe('denied');
      const after = await currentHtml(app); unchanged(after.page, before.page);
      expect(after.stored).toEqual(before.stored); expect(after.published.html).toBe(before.published.html);
      await positiveControl(app, page, actor, before.page);
    });
  }
}

for (const [id, href] of [
  ['local', '/acceptance/link-target/'],
  ['http', 'http://example.invalid/editor-reference'],
  ['https', 'https://example.invalid/editor-reference'],
]) {
  test(`EDITOR-SAFE-106-allowed-${id} | AT-106 AC-DTL-006 | employee publishes an allowed ordinary link with safe blank-target relation`, async ({ app, page }) => {
    await app.reset('assigned-page-with-owner-draft');
    const before = await app.observe('page', { page: 'P-ASSIGNED' });
    const html = `<p><a href="${href}" target="_blank">EDITOR-LINK-CANARY</a></p>`;
    expect((await publish(app, 'S-EDIT', html, before.revision)).outcome).toBe('accepted');
    const actual = await currentHtml(app);
    expect(actual.page.versions).toHaveLength(before.versions.length + 1);
    for (const value of [actual.stored.html, actual.stored.versionHtml, actual.published.html]) {
      const links = (await parse(page, value)).links;
      expect(links).toHaveLength(1); expect(links[0].text).toBe('EDITOR-LINK-CANARY');
      expect(typeof links[0].href).toBe('string');
      expect(new URL(links[0].href, process.env.ESTAKADA_TEST_BASE_URL).href)
        .toBe(new URL(href, process.env.ESTAKADA_TEST_BASE_URL).href);
      expect(links[0].target).toBe('_blank'); expect(links[0].rel).toContain('noopener');
    }
    for (const field of ['url', 'h1', 'title', 'description', 'price', 'assetId', 'draftText']) expect(actual.page[field]).toEqual(before[field]);
  });
}

const forbiddenLinks = [
  ['javascript', 'javascript:window.EDITOR_EXECUTION_CANARY=1'],
  ['mixed-case', 'JaVaScRiPt:window.EDITOR_EXECUTION_CANARY=1'],
  ['entity', 'jav&#x61;script:window.EDITOR_EXECUTION_CANARY=1'],
  ['encoded-control', 'java&#x09;script:window.EDITOR_EXECUTION_CANARY=1'],
  ['data', 'data:text/html,EDITOR-REJECT-CANARY'],
  ['file', 'file:///synthetic-editor-probe'],
  ['vbscript', 'vbscript:synthetic'],
  ['protocol-relative', '//example.invalid/editor-reference'],
  ['userinfo', 'https://synthetic@example.invalid/editor-reference'],
  ['backslash', 'https:\\example.invalid\\editor-reference'],
];
for (const [id, href] of forbiddenLinks) {
  test(`EDITOR-SAFE-106-reject-${id} | AT-106 AC-DTL-006 | unsafe or ambiguous link refuses the whole direct publication`, async ({ app, page }) => {
    await app.reset('assigned-page-with-owner-draft');
    const before = await currentHtml(app);
    const html = `<p>EDITOR-REJECT-CANARY <a href="${href}">ссылка</a></p>`;
    expect((await publish(app, 'S-EDIT', html, before.page.revision)).outcome).toBe('denied');
    const after = await currentHtml(app); unchanged(after.page, before.page);
    expect(after.stored).toEqual(before.stored); expect(after.published.html).toBe(before.published.html);
    await positiveControl(app, page, 'S-EDIT', before.page);
  });
}
