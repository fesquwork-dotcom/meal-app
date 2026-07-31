import axios from 'axios';

/** True when the request was intentionally cancelled (AbortSignal / axios canceled). */
export function isRequestAbortError(error: unknown): boolean {
  if (!error || typeof error !== 'object') {
    return false;
  }
  if (axios.isCancel(error)) {
    return true;
  }
  const err = error as { name?: unknown; code?: unknown; message?: unknown };
  if (err.name === 'CanceledError' || err.name === 'AbortError') {
    return true;
  }
  if (err.code === 'ERR_CANCELED' || err.code === 'ERR_ABORTED') {
    return true;
  }
  if (typeof err.message === 'string' && /aborted|canceled|cancelled/i.test(err.message)) {
    return true;
  }
  return false;
}
