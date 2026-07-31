import { describe, expect, it } from 'vitest';

import {
  buildProfileFieldErrorMap,
  mapWorkflowFieldToProfileKey,
} from '@/features/strategy-workflow/strategyWorkflowFieldMapping';

describe('strategy workflow field mapping', () => {
  it('maps known profile fields', () => {
    expect(mapWorkflowFieldToProfileKey('profile.proteins')).toBe('proteins');
    expect(mapWorkflowFieldToProfileKey('profile.budget')).toBe('budget');
  });

  it('keeps unknown fields safely', () => {
    expect(mapWorkflowFieldToProfileKey('other.field')).toBeNull();
    const mapped = buildProfileFieldErrorMap([
      { field: 'profile.cooktime', code: 'X', message: 'a' },
      { field: 'mystery', code: 'Y', message: 'b' },
    ]);
    expect(mapped.cooktime).toBe('a');
    expect(mapped.mystery).toBe('b');
  });

  it('handles empty list', () => {
    expect(buildProfileFieldErrorMap([])).toEqual({});
  });
});
