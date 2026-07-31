import { describe, expect, it } from 'vitest';

import {
  planExternalProfileUpdate,
  PROFILE_SERVER_UPDATE_NONE,
} from '@/features/profile/profileServerUpdate';
import type { ExternalProfileUpdatePlanInput } from '@/features/profile/profileServerUpdate';
import profileProviderSource from '@/features/profile/ProfileProvider.tsx?raw';
import memorySectionSource from '@/features/memory/MemorySignalsSection.tsx?raw';
import behaviorSectionSource from '@/features/behavior/BehaviorInsightsSection.tsx?raw';
import generateSheetSource from '@/features/menu-generator/GenerateMenuSheet.tsx?raw';

const NOW = 1_700_000_000_000;

function input(overrides: Partial<ExternalProfileUpdatePlanInput>): ExternalProfileUpdatePlanInput {
  return {
    source: 'refresh',
    draftDirty: false,
    draftBaseRevision: 8,
    previousServerRevision: 8,
    nextServerRevision: 9,
    previousUpdateState: PROFILE_SERVER_UPDATE_NONE,
    alreadyNotifiedRevision: null,
    now: NOW,
    ...overrides,
  };
}

describe('planExternalProfileUpdate — draft handling', () => {
  it('clean draft: syncs draft without warning', () => {
    const plan = planExternalProfileUpdate(input({ draftDirty: false }));
    expect(plan.syncDraft).toBe(true);
    expect(plan.nextUpdateState.status).toBe('none');
  });

  it('dirty draft + newer revision: keeps draft and detects warning', () => {
    const plan = planExternalProfileUpdate(input({ draftDirty: true }));
    expect(plan.syncDraft).toBe(false);
    expect(plan.nextUpdateState).toEqual({
      status: 'detected',
      draftBaseRevision: 8,
      currentServerRevision: 9,
      detectedAt: NOW,
    });
  });

  it('dirty draft + same revision: keeps draft, no warning', () => {
    const plan = planExternalProfileUpdate(
      input({ draftDirty: true, nextServerRevision: 8, previousServerRevision: 8 }),
    );
    expect(plan.syncDraft).toBe(false);
    expect(plan.nextUpdateState.status).toBe('none');
    expect(plan.notifyExternalProfileUpdate).toBe(false);
  });
});

describe('planExternalProfileUpdate — coordinator policy', () => {
  it('background refresh with newer revision emits external_profile_update', () => {
    expect(planExternalProfileUpdate(input({ source: 'refresh' })).notifyExternalProfileUpdate).toBe(
      true,
    );
  });

  it('refresh with unchanged revision emits nothing', () => {
    const plan = planExternalProfileUpdate(
      input({ source: 'refresh', nextServerRevision: 8, previousServerRevision: 8 }),
    );
    expect(plan.notifyExternalProfileUpdate).toBe(false);
  });

  it('refresh does not emit twice for the same revision', () => {
    const plan = planExternalProfileUpdate(input({ source: 'refresh', alreadyNotifiedRevision: 9 }));
    expect(plan.notifyExternalProfileUpdate).toBe(false);
  });

  it('memory promotion never emits external_profile_update (memory_promoted is the single reason)', () => {
    const clean = planExternalProfileUpdate(input({ source: 'memory_promotion' }));
    const dirty = planExternalProfileUpdate(input({ source: 'memory_promotion', draftDirty: true }));
    expect(clean.notifyExternalProfileUpdate).toBe(false);
    expect(dirty.notifyExternalProfileUpdate).toBe(false);
    expect(dirty.nextUpdateState.status).toBe('detected');
  });

  it('behavior recommendation never emits external_profile_update', () => {
    const clean = planExternalProfileUpdate(input({ source: 'behavior_recommendation' }));
    const dirty = planExternalProfileUpdate(
      input({ source: 'behavior_recommendation', draftDirty: true }),
    );
    expect(clean.notifyExternalProfileUpdate).toBe(false);
    expect(dirty.notifyExternalProfileUpdate).toBe(false);
  });

  it('conflict resolution never emits external_profile_update', () => {
    const plan = planExternalProfileUpdate(input({ source: 'conflict_resolution' }));
    expect(plan.notifyExternalProfileUpdate).toBe(false);
  });

  it('generation workflow never emits external_profile_update (its flow owns the reason)', () => {
    const clean = planExternalProfileUpdate(input({ source: 'generation' }));
    const dirty = planExternalProfileUpdate(input({ source: 'generation', draftDirty: true }));
    expect(clean.notifyExternalProfileUpdate).toBe(false);
    expect(clean.syncDraft).toBe(true);
    expect(dirty.notifyExternalProfileUpdate).toBe(false);
  });
});

describe('ProfileProvider external update wiring (source contract)', () => {
  it('exposes a central applyExternalProfileUpdate method', () => {
    expect(profileProviderSource).toContain('applyExternalProfileUpdate');
    expect(profileProviderSource).toContain('planExternalProfileUpdate');
  });

  it('background refresh routes through applyExternalProfileUpdate', () => {
    expect(profileProviderSource).toContain("applyExternalProfileUpdate(serverState, { source: 'refresh' })");
  });

  it('never rebases draftBaseRevision inside the external update path', () => {
    const start = profileProviderSource.indexOf('const applyExternalProfileUpdate');
    const end = profileProviderSource.indexOf('const reloadProfile');
    expect(start).toBeGreaterThan(-1);
    const body = profileProviderSource.slice(start, end);
    expect(body).not.toContain('setDraftBaseRevision');
    expect(body).not.toContain('setHasProfileDraft(false)');
    expect(body).not.toContain('setProfileState');
  });

  it('memory promotion applies the response via the central method with one reason', () => {
    expect(memorySectionSource).toContain("{ source: 'memory_promotion' }");
    expect(memorySectionSource).toContain("notifyStrategyInputsChanged('memory_promoted')");
    expect(memorySectionSource).not.toContain('onProfileSaved');
    expect(memorySectionSource).not.toContain("'profile_saved'");
    expect(memorySectionSource).not.toContain("'external_profile_update'");
  });

  it('generation sheet applies conflict-resolution profile updates via the central method', () => {
    expect(generateSheetSource).toContain("{ source: 'generation' }");
    expect(generateSheetSource).toContain("notifyStrategyInputsChanged('conflict_resolved')");
    expect(generateSheetSource).not.toContain('onProfileSaved');
    expect(generateSheetSource).not.toContain("'external_profile_update'");
  });

  it('behavior recommendation applies the response via the central method with one reason', () => {
    expect(behaviorSectionSource).toContain("{ source: 'behavior_recommendation' }");
    expect(behaviorSectionSource).toContain(
      "notifyStrategyInputsChanged('behavior_recommendation_applied')",
    );
    expect(behaviorSectionSource).not.toContain('onProfileSaved');
    expect(behaviorSectionSource).not.toContain("'profile_saved'");
    expect(behaviorSectionSource).not.toContain("'external_profile_update'");
  });

  it('server update state is session-only (never persisted to localStorage)', () => {
    expect(profileProviderSource).not.toMatch(/STORAGE_KEYS\.[A-Z_]*SERVER_UPDATE/);
    expect(profileProviderSource).not.toMatch(/setStorageItem\([^)]*serverUpdate/i);
  });

  it('provider never touches the local MenuPlan', () => {
    expect(profileProviderSource).not.toContain("from '@/features/menu-plan");
    expect(profileProviderSource).not.toContain('clearMenuPlan');
    expect(profileProviderSource).not.toContain('MENU_PLAN');
  });

  it('save keeps CAS: PUT still uses draftBaseRevision as expected revision', () => {
    expect(profileProviderSource).toContain('saveProfile(profile, draftBaseRevision)');
  });

  it('load server version is an explicit user action with profile_rebased invalidation', () => {
    expect(profileProviderSource).toContain('const loadServerProfileVersion');
    const start = profileProviderSource.indexOf('const loadServerProfileVersion');
    const body = profileProviderSource.slice(start, profileProviderSource.indexOf('const saveProfileDraft'));
    expect(body).toContain("notifyStrategyInputsChanged('profile_rebased')");
    expect(body).toContain('logProfileServerVersionLoaded');
  });
});
