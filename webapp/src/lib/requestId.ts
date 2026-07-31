/**
 * Generates a client-side idempotency id for a single user action (e.g. a meal
 * replacement). Used so backend Memory Engine can deduplicate double-clicks and
 * network retries. Falls back to a non-crypto id in older webviews.
 */
export function createRequestId(): string {
  const globalCrypto = typeof globalThis !== 'undefined' ? globalThis.crypto : undefined;
  if (globalCrypto && typeof globalCrypto.randomUUID === 'function') {
    return globalCrypto.randomUUID();
  }
  return `rid-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
}
