import fs from 'node:fs';
import path from 'node:path';

// Container resource guard, NOT a website upload-policy or a server-side rejection test.
export const transportFileLimit = 64 * 1024 * 1024;
export const transportMultipartLimit = 64 * 1024 * 1024;
export function filePayload(root, runId, descriptor, { maxBytes = transportFileLimit } = {}) {
  if (typeof runId !== 'string' || !/^[A-Za-z0-9_-]{16,128}$/.test(runId)) throw new Error('DRIVER_UPLOAD_RUN_REQUIRED');
  if (!descriptor || typeof descriptor.path !== 'string' || typeof descriptor.name !== 'string' ||
    !descriptor.name || typeof descriptor.mimeType !== 'string') throw new Error('DRIVER_UPLOAD_DESCRIPTOR_REQUIRED');
  const realRoot = fs.realpathSync(root);
  const intended = path.join(realRoot, 'generated-fixtures', runId);
  let runDirectory, filename;
  try { runDirectory = fs.realpathSync(intended); filename = fs.realpathSync(descriptor.path); }
  catch { throw new Error('DRIVER_UPLOAD_FIXTURE_NOT_AVAILABLE'); }
  if (runDirectory !== intended || !filename.startsWith(runDirectory + path.sep)) throw new Error('DRIVER_UPLOAD_OUTSIDE_RUN');
  // Open then inspect the actual descriptor: no second path lookup after validation.
  const fd = fs.openSync(filename, fs.constants.O_RDONLY | (fs.constants.O_NOFOLLOW || 0));
  try {
    const stat = fs.fstatSync(fd);
    if (!Number.isSafeInteger(maxBytes) || maxBytes < 0 || !stat.isFile() || stat.size > Math.min(transportFileLimit, maxBytes))
      throw new Error('DRIVER_UPLOAD_TRANSPORT_RESOURCE_LIMIT');
    const buffer = Buffer.alloc(stat.size);
    let read = 0;
    while (read < buffer.length) {
      const count = fs.readSync(fd, buffer, read, buffer.length - read, read);
      if (!count) break;
      read += count;
    }
    if (read !== stat.size || fs.fstatSync(fd).size !== stat.size) throw new Error('DRIVER_UPLOAD_FIXTURE_CHANGED');
    return { name: descriptor.name, mimeType: descriptor.mimeType, buffer };
  } finally { fs.closeSync(fd); }
}

export function multipartPayload(fields, files, resolve) {
  const result = Object.create(null);
  let fieldBytes = 0, remaining = transportMultipartLimit;
  if (Object.keys(files || {}).length > 32) throw new Error('DRIVER_MULTIPART_TRANSPORT_RESOURCE_LIMIT');
  for (const [name, value] of Object.entries(fields || {})) {
    if (!['string', 'number', 'boolean'].includes(typeof value)) throw new Error('DRIVER_MULTIPART_FIELD_TYPE');
    fieldBytes += Buffer.byteLength(name) + Buffer.byteLength(String(value));
    if (fieldBytes > 256 * 1024) throw new Error('DRIVER_MULTIPART_TRANSPORT_RESOURCE_LIMIT');
    result[name] = value;
  }
  for (const [name, reference] of Object.entries(files || {})) {
    if (Object.hasOwn(result, name)) throw new Error('DRIVER_MULTIPART_FIELD_COLLISION');
    const payload = resolve(reference, remaining);
    if (!Buffer.isBuffer(payload?.buffer) || payload.buffer.length > remaining) throw new Error('DRIVER_MULTIPART_TRANSPORT_RESOURCE_LIMIT');
    remaining -= payload.buffer.length;
    result[name] = payload;
  }
  if (!Object.keys(files || {}).length) throw new Error('DRIVER_MULTIPART_FILES_REQUIRED');
  return result;
}
