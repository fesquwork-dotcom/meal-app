import { describe, expect, it } from 'vitest';

import {
  assertCurrentMenuUnchanged,
  createInvalidationHarness,
} from '@/features/strategy-inputs/invalidationHarness';
import type { MenuPlan } from '@/types/menu';

const sampleMenu: MenuPlan = {
  summary: 'План',
  plan_start_date: '2026-07-13',
  strategy_id: 'strategy-protect-me',
  total_cost: 1000,
  days_plan: [
    {
      day: 'День 1',
      breakfast: 'Овсянка',
      lunch: 'Борщ',
      dinner: 'Рыба',
      meals: [
        {
          type: 'breakfast',
          recipe_name: 'Овсянка',
          meal_id: 'day1_breakfast',
          requires_cooking: true,
          prepared_on_day: 1,
        },
      ],
    },
  ],
  recipes: [],
  basket: [],
};

describe('strategy inputs provider integration harness', () => {
  it('profile_saved increments revision and resets preview/compare, keeps MenuPlan', () => {
    const h = createInvalidationHarness(sampleMenu);
    h.setReadyPreview(0);
    h.setCompareResult(0);
    const before = structuredClone(h.menuPlan);
    const draftBefore = { ...h.draft };

    h.notifyInput('profile_saved');

    expect(h.inputs.revision).toBe(1);
    expect(h.preview.phase).toBe('stale');
    expect(h.preview.preview).toBeNull();
    expect(h.compare.result).toBeNull();
    assertCurrentMenuUnchanged(before, h.menuPlan);
    expect(h.draft).toEqual(draftBefore);
  });

  it('behavior_snoozed is a no-op for revision/preview/compare/menu', () => {
    const h = createInvalidationHarness(sampleMenu);
    h.setReadyPreview(0);
    h.setCompareResult(0);
    const previewBefore = { ...h.preview };
    const compareBefore = { ...h.compare };

    h.notifyInput('behavior_snoozed');

    expect(h.inputs.revision).toBe(0);
    expect(h.preview.preview).toEqual(previewBefore.preview);
    expect(h.compare.result).toEqual(compareBefore.result);
    expect(h.menuPlan.strategy_id).toBe('strategy-protect-me');
  });

  it('server_stale_behavior clears ready preview without revision bump', () => {
    const h = createInvalidationHarness(sampleMenu);
    h.setReadyPreview(0);
    h.setCompareResult(0);

    h.notifyStale('server_stale_behavior');

    expect(h.inputs.revision).toBe(0);
    expect(h.preview.phase).toBe('stale');
    expect(h.compare.result).toBeNull();
    expect(h.menuPlan.strategy_id).toBe('strategy-protect-me');
  });

  it('duplicate stale after local clear does not bump revision or menu', () => {
    const h = createInvalidationHarness(sampleMenu);
    h.setReadyPreview(0);
    h.notifyInput('profile_saved');
    expect(h.inputs.revision).toBe(1);
    const afterLocal = structuredClone(h.menuPlan);
    const phase = h.preview.phase;

    h.notifyStale('server_stale_profile');

    expect(h.inputs.revision).toBe(1);
    expect(h.preview.phase).toBe(phase);
    assertCurrentMenuUnchanged(afterLocal, h.menuPlan);
    expect(h.preview.error).toContain('другой сессии');
  });

  it.each([
    ['profile_saved', 'input'] as const,
    ['memory_promoted', 'input'] as const,
    ['behavior_revoked', 'input'] as const,
    ['learned_preference_accepted', 'input'] as const,
    ['learned_preference_revoked', 'input'] as const,
    ['server_stale_profile', 'stale'] as const,
    ['server_stale_memory', 'stale'] as const,
    ['server_stale_behavior', 'stale'] as const,
    ['server_stale_learned_preferences', 'stale'] as const,
    ['preview_token_expired', 'stale'] as const,
    ['preview_version_mismatch', 'stale'] as const,
  ])('%s keeps MenuPlan', (reason, kind) => {
    const h = createInvalidationHarness(sampleMenu);
    h.setReadyPreview(0);
    const before = structuredClone(h.menuPlan);
    if (kind === 'input') {
      h.notifyInput(
        reason as
          | 'profile_saved'
          | 'memory_promoted'
          | 'behavior_revoked'
          | 'learned_preference_accepted'
          | 'learned_preference_revoked',
      );
    } else {
      h.notifyStale(
        reason as
          | 'server_stale_profile'
          | 'server_stale_memory'
          | 'server_stale_behavior'
          | 'server_stale_learned_preferences'
          | 'preview_token_expired'
          | 'preview_version_mismatch',
      );
    }
    assertCurrentMenuUnchanged(before, h.menuPlan);
  });
});
