export function checkedCanaries(value) {
  if (!Array.isArray(value) || value.length > 128 || value.some(item => typeof item !== 'string' || item.length < 4) ||
    value.reduce((sum, item) => sum + item.length, 0) > 16384) throw new Error('DRIVER_SENSITIVE_CORPUS_INVALID');
  return value;
}

export function sensitiveValueCheck(value, canaries) {
  checkedCanaries(canaries);
  const visit = item => typeof item === 'string' ? canaries.some(canary => item.includes(canary))
    : Array.isArray(item) ? item.some(visit) : item && typeof item === 'object' ? Object.values(item).some(visit) : false;
  return { checkedCount: canaries.length, detected: Boolean(visit(value)) };
}

// Runs only in the isolated parser page. No returned text or secret values.
export function htmlSensitiveCheck({ source, canaries }) {
  const document = new DOMParser().parseFromString(source, 'text/html');
  const values = [source, document.documentElement.textContent || ''];
  for (const node of document.querySelectorAll('*')) for (const attribute of node.attributes) values.push(attribute.value);
  return { checkedCount: canaries.length, detected: canaries.some(canary => values.some(value => value.includes(canary))) };
}
