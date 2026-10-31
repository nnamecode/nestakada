// Read only the actual actor tab. No app state or expected business result is constructed here.
export async function inspectBrowserPersistence(page, expectedOrigin, canary) {
  if (typeof canary !== 'string' || canary.length < 8 || canary.length > 4096)
    throw new Error('DRIVER_MEMORY_CANARY_INVALID');
  if (new URL(page.url()).origin !== expectedOrigin) throw new Error('DRIVER_MEMORY_ORIGIN_MISMATCH');
  return page.evaluate(({ expectedOrigin, canary }) => {
    if (location.origin !== expectedOrigin) throw new Error('DRIVER_MEMORY_ORIGIN_MISMATCH');
    const contains = value => {
      let current = String(value);
      for (let pass = 0; pass < 3; pass++) {
        if (current.includes(canary)) return true;
        try {
          const decoded = decodeURIComponent(current.replace(/\+/g, ' '));
          if (decoded === current) break;
          current = decoded;
        } catch { break; }
      }
      return false;
    };
    const storageContains = storage => {
      for (let i = 0; i < storage.length; i++) {
        const key = storage.key(i);
        if (contains(key) || contains(storage.getItem(key))) return true;
      }
      return false;
    };
    // Storage access errors propagate: an unreadable store must never be reported as empty.
    return {
      source: 'actual-actor-browser',
      urlContainsCanary: contains(location.href),
      localStorageContainsCanary: storageContains(localStorage),
      sessionStorageContainsCanary: storageContains(sessionStorage),
    };
  }, { expectedOrigin, canary });
}
