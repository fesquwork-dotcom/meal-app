import { describe, expect, it } from 'vitest';

import { PROFILE_SERVER_UPDATE_NONE } from '@/features/profile/profileServerUpdate';
import type { ProfileServerUpdateState } from '@/features/profile/profileServerUpdate';
import {
  buildProfileServerUpdateViewModel,
  PROFILE_SERVER_UPDATE_DESCRIPTION,
  PROFILE_SERVER_UPDATE_TITLE,
} from '@/features/profile/profileServerUpdateViewModel';

const DETECTED: ProfileServerUpdateState = {
  status: 'detected',
  draftBaseRevision: 8,
  currentServerRevision: 9,
  detectedAt: 1_700_000_000_000,
};

describe('buildProfileServerUpdateViewModel', () => {
  it('is hidden for status none', () => {
    const vm = buildProfileServerUpdateViewModel(PROFILE_SERVER_UPDATE_NONE, null);
    expect(vm.visible).toBe(false);
    expect(vm.canLoadServerVersion).toBe(false);
    expect(vm.canContinueEditing).toBe(false);
  });

  it('is visible with both actions when detected', () => {
    const vm = buildProfileServerUpdateViewModel(DETECTED, null);
    expect(vm.visible).toBe(true);
    expect(vm.canLoadServerVersion).toBe(true);
    expect(vm.canContinueEditing).toBe(true);
  });

  it('uses the soft warning texts without loss wording', () => {
    const vm = buildProfileServerUpdateViewModel(DETECTED, null);
    expect(vm.title).toBe(PROFILE_SERVER_UPDATE_TITLE);
    expect(vm.description).toBe(PROFILE_SERVER_UPDATE_DESCRIPTION);
    expect(vm.title).toContain('Сохранённые настройки изменились');
    expect(vm.description).toContain('несохранённые изменения сохранены');
    expect(vm.description).not.toContain('потеряны');
  });

  it('does not expose profile values or field-level details', () => {
    const vm = buildProfileServerUpdateViewModel(DETECTED, null);
    expect(JSON.stringify(vm)).not.toContain('9');
    expect(JSON.stringify(vm)).not.toContain('8');
  });

  it('is hidden when dismissed for the current server revision', () => {
    const vm = buildProfileServerUpdateViewModel(DETECTED, 9);
    expect(vm.visible).toBe(false);
  });

  it('shows again when a newer revision arrives after dismissal', () => {
    const newer: ProfileServerUpdateState = {
      ...DETECTED,
      currentServerRevision: 10,
    };
    const vm = buildProfileServerUpdateViewModel(newer, 9);
    expect(vm.visible).toBe(true);
  });

  it('ignores stale dismissal for an older revision', () => {
    const vm = buildProfileServerUpdateViewModel(DETECTED, 7);
    expect(vm.visible).toBe(true);
  });
});
