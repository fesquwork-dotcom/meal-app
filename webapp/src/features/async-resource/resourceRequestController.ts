export type ResourceAbortReason = 'superseded' | 'unmount' | 'dispose';

/**
 * Owns monotonic request IDs + AbortController for one resource hook/provider.
 * Not a global manager — create one instance per resource owner.
 */
export class ResourceRequestController {
  private requestId = 0;
  private controller: AbortController | null = null;
  private disposed = false;

  get currentRequestId(): number {
    return this.requestId;
  }

  get isDisposed(): boolean {
    return this.disposed;
  }

  /** Aborts any in-flight request and starts a new one. */
  begin(reason: ResourceAbortReason = 'superseded'): {
    requestId: number;
    signal: AbortSignal;
  } {
    if (this.disposed) {
      throw new Error('ResourceRequestController disposed');
    }
    this.abortCurrent(reason);
    this.requestId += 1;
    this.controller = new AbortController();
    return {
      requestId: this.requestId,
      signal: this.controller.signal,
    };
  }

  abortCurrent(reason: ResourceAbortReason): void {
    if (!this.controller) {
      return;
    }
    if (import.meta.env.DEV) {
      console.info('resource_request_aborted', {
        requestId: this.requestId,
        reason,
      });
    }
    this.controller.abort();
    this.controller = null;
  }

  isCurrent(requestId: number): boolean {
    return !this.disposed && this.requestId === requestId;
  }

  dispose(): void {
    this.abortCurrent('dispose');
    this.disposed = true;
  }
}

export function createResourceRequestController(): ResourceRequestController {
  return new ResourceRequestController();
}
