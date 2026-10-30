import { defineConfig } from '@playwright/test';

const reportName = ['harness', 'documents', 'driver-safety', 'public-http', 'public-contracts', 'application-contracts', 'form-contracts', 'form-windows', 'shared-blocks', 'backup-contracts', 'html-build', 'content-lifecycle', 'fallback-contracts', 'media-contracts', 'logging-contracts', 'request-lifecycle', 'seo-contracts', 'list'].includes(process.env.ESTAKADA_TEST_REPORT)
  ? process.env.ESTAKADA_TEST_REPORT : 'local';

export default defineConfig({
  testDir: '.',
  fullyParallel: false,
  workers: 1,
  retries: 0,
  timeout: 20_000,
  expect: { timeout: 5_000 },
  outputDir: `../test-results/acceptance/artifacts/${reportName}`,
  reporter: [['list'], ['json', { outputFile: `../test-results/acceptance/${reportName}-results.json` }]],
  use: { trace: 'off', screenshot: 'off', video: 'off', ignoreHTTPSErrors: false },
  projects: [
    { name: 'harness', testMatch: 'harness.spec.js' },
    { name: 'driver-safety', testMatch: 'driver-safety.spec.js' },
    { name: 'public-http', testMatch: 'public-http.spec.js' },
    { name: 'public-contracts', testMatch: 'public-contracts.spec.js', use: { browserName: 'chromium', javaScriptEnabled: false } },
    { name: 'application-contracts', testMatch: 'application-contracts.spec.js' },
    { name: 'form-contracts', testMatch: 'form-contracts.spec.js' },
    { name: 'form-windows', testMatch: 'form-window-contracts.spec.js' },
    { name: 'shared-blocks', testMatch: 'shared-block-contracts.spec.js', use: { browserName: 'chromium', javaScriptEnabled: false, serviceWorkers: 'block' } },
    { name: 'backup-contracts', testMatch: 'backup-contracts.spec.js' },
    { name: 'html-build', testMatch: 'html-build-contracts.spec.js', use: { browserName: 'chromium', javaScriptEnabled: false, serviceWorkers: 'block' } },
    { name: 'content-lifecycle', testMatch: 'content-lifecycle.spec.js' },
    { name: 'fallback-contracts', testMatch: 'fallback-contracts.spec.js' },
    { name: 'media-contracts', testMatch: 'media-contracts.spec.js' },
    { name: 'logging-contracts', testMatch: 'logging-contracts.spec.js' },
    { name: 'request-lifecycle', testMatch: 'request-lifecycle.spec.js' },
    { name: 'seo-contracts', testMatch: 'seo-contracts.spec.js', use: { browserName: 'chromium', javaScriptEnabled: false, serviceWorkers: 'block' } },
    ...['chromium', 'firefox', 'webkit'].map(browserName => ({
      name: `harness-${browserName}`, testMatch: 'browser-harness.spec.js',
      use: { browserName },
    })),
  ],
});
