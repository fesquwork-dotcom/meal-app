import { describe, expect, it, vi } from 'vitest';

import { clearClientStateAfterDevReset } from '@/features/diagnostics/clearClientStateAfterDevReset';
import { STORAGE_KEYS } from '@/constants/storage';

describe('DevResetWorkflow', () => {
  it('clears client storage keys after reset', () => {
    const remove = vi.fn();
    vi.stubGlobal('localStorage', {
      removeItem: remove,
      getItem: vi.fn(),
      setItem: vi.fn(),
    });
    clearClientStateAfterDevReset();
    expect(remove).toHaveBeenCalledWith(STORAGE_KEYS.MENU_PLAN);
    expect(remove).toHaveBeenCalledWith(STORAGE_KEYS.BASKET_CHECKED);
    expect(remove).toHaveBeenCalledWith(STORAGE_KEYS.PROFILE_DRAFT);
    expect(remove).toHaveBeenCalledWith(STORAGE_KEYS.POSITIVE_EVENT_MARKS);
    vi.unstubAllGlobals();
  });
});
