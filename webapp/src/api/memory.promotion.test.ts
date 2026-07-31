import { describe, expect, it, vi } from 'vitest';

import { promoteMemorySignal } from '@/api/memory';

vi.mock('@/api/client', () => ({
  api: {
    post: vi.fn(),
  },
}));

import { api } from '@/api/client';

describe('promoteMemorySignal', () => {
  it('sends only expected revision in the request body', async () => {
    vi.mocked(api.post).mockResolvedValue({
      data: {
        status: 'promoted',
        profile: {
          user_id: 42,
          first_name: 'Test',
          days: 3,
          budget: 3000,
          proteins: ['any'],
          goal: 'home',
          meal_types: ['breakfast', 'lunch', 'dinner'],
          meals_per_day: 3,
          persons: 2,
          cooktime: 'medium',
          dietary_constraints: [
            { id: 'dc_1', kind: 'preference', value: 'гречка' },
          ],
          store: 'any',
          updated_at: null,
        },
        profile_revision: 2,
        signal_status: 'promoted',
        constraint_id: 'dc_1',
      },
    });

    const result = await promoteMemorySignal('sig-1', 1);

    expect(api.post).toHaveBeenCalledWith('/api/memory/signals/sig-1/promote', {
      expected_profile_revision: 1,
    });
    expect(result.revision).toBe(2);
    expect(result.promotionStatus).toBe('promoted');
    expect(result.profile.dietary_constraints).toHaveLength(1);
  });
});
