import { describe, expect, it, vi } from 'vitest';

import { createResourceRequestController } from '@/features/async-resource/resourceRequestController';

describe('resourceRequestController', () => {
  it('increments request id and aborts previous on begin', () => {
    const controller = createResourceRequestController();
    const first = controller.begin();
    const spy = vi.fn();
    first.signal.addEventListener('abort', spy);
    const second = controller.begin('superseded');
    expect(second.requestId).toBe(first.requestId + 1);
    expect(spy).toHaveBeenCalled();
    expect(first.signal.aborted).toBe(true);
    expect(second.signal.aborted).toBe(false);
  });

  it('dispose aborts current and rejects further begin', () => {
    const controller = createResourceRequestController();
    const active = controller.begin();
    controller.dispose();
    expect(active.signal.aborted).toBe(true);
    expect(controller.isDisposed).toBe(true);
    expect(() => controller.begin()).toThrow(/disposed/);
  });

  it('isCurrent tracks latest request', () => {
    const controller = createResourceRequestController();
    const first = controller.begin();
    const second = controller.begin();
    expect(controller.isCurrent(first.requestId)).toBe(false);
    expect(controller.isCurrent(second.requestId)).toBe(true);
  });
});
