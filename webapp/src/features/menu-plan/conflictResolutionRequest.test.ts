import { describe, expect, it } from 'vitest';

import type { ResolveConflictRequest } from '@/types/strategyPreview';

describe('server-owned conflict resolution request', () => {
  it('contains only token, conflict ID and action', () => {
    const request: ResolveConflictRequest = {
      preview_token: 'signed-token',
      conflict_id: 'cfl_abc123def456',
      action: 'dismiss_memory_signal',
    };
    expect(Object.keys(request)).toEqual(['preview_token', 'conflict_id', 'action']);
    expect(request).not.toHaveProperty('proteins');
    expect(request).not.toHaveProperty('memory_signal_id');
  });
});
