/**
 * Options for read-only resource loaders (GET).
 *
 * Mutation cancellation policy (Sprint 5.35 architectural decision):
 * mutation requests (Profile PUT, Memory promotion, Behavior recommendation,
 * confirm/dismiss/snooze/revoke) intentionally do NOT accept an AbortSignal.
 * A mutation may complete on the server even after a client-side abort, which
 * would leave the UI believing the operation was cancelled while the server
 * already applied the change. Until idempotency keys / status reconciliation
 * exist, mutations rely on typed pending state, disabled repeated clicks,
 * WorkflowResult and server-owned CAS instead of client cancellation.
 */
export type ResourceLoaderOptions = {
  signal?: AbortSignal;
};
