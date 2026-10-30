import fs from 'node:fs';
import { localTarget } from './test-support.js';

// This is a test interface, not a website endpoint or implementation of business rules.
// A future reviewed adapter must exercise the real isolated app and read its actual state.
export async function openApplicationDriver() {
  const adapterUrl = new URL('./isolated-application-driver.js', import.meta.url);
  if (!fs.existsSync(adapterUrl)) {
    throw new Error('APPLICATION_DRIVER_NOT_IMPLEMENTED: assertions authored; real isolated fixture/UI/HTTP adapter is absent. No mock application is allowed.');
  }
  const base = localTarget(process.env.ESTAKADA_TEST_BASE_URL);
  const adapter = await import(adapterUrl.href);
  if (adapter.driverKind !== 'real-isolated-application-v1' || typeof adapter.createDriver !== 'function')
    throw new Error('A reviewed real isolated application driver is required');
  const driver = await adapter.createDriver({ baseURL: base.href });
  for (const method of ['reset', 'act', 'observe', 'close'])
    if (typeof driver?.[method] !== 'function') throw new Error(`Driver method missing: ${method}`);
  return driver;
}
