// Test-side inert parsing only; this does not render or sanitize website content.
export async function parseMetadata(page, html) {
  await page.route('**/*', route => route.abort());
  return page.evaluate(source => {
    const document = new DOMParser().parseFromString(source, 'text/html');
    const links = [...document.querySelectorAll('link')].filter(node =>
      (node.getAttribute('rel') || '').toLowerCase().split(/\s+/).includes('canonical'));
    const viewports = [...document.querySelectorAll('meta')].filter(node =>
      (node.getAttribute('name') || '').toLowerCase() === 'viewport');
    const refresh = [...document.querySelectorAll('meta')].filter(node =>
      (node.getAttribute('http-equiv') || '').trim().toLowerCase() === 'refresh');
    return {
      canonical: links.map(node => ({ href: node.getAttribute('href'), inHead: document.head.contains(node) })),
      viewport: viewports.map(node => ({ content: node.getAttribute('content'), inHead: document.head.contains(node) })),
      refreshCount: refresh.length,
    };
  }, html);
}
