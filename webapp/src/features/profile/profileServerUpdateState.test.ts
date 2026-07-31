import { describe, expect, it } from 'vitest';

import {
  detectProfileServerUpdate,
  isNewServerUpdateDetection,
  PROFILE_SERVER_UPDATE_NONE,
} from '@/features/profile/profileServerUpdate';
import type { ProfileServerUpdateState } from '@/features/profile/profileServerUpdate';

const NOW = 1_700_000_000_000;

describe('detectProfileServerUpdate', () => {
  it('detects update for dirty draft with newer server revision', () => {
    const state = detectProfileServerUpdate({
      draftDirty: true,
      draftBaseRevision: 8,
      nextServerRevision: 9,
      previousState: PROFILE_SERVER_UPDATE_NONE,
      now: NOW,
    });
    expect(state).toEqual({
      status: 'detected',
      draftBaseRevision: 8,
      currentServerRevision: 9,
      detectedAt: NOW,
    });
  });

  it('returns none for dirty draft with same revision', () => {
    const state = detectProfileServerUpdate({
      draftDirty: true,
      draftBaseRevision: 8,
      nextServerRevision: 8,
      previousState: PROFILE_SERVER_UPDATE_NONE,
      now: NOW,
    });
    expect(state.status).toBe('none');
  });

  it('returns none for dirty draft with lower server revision', () => {
    const state = detectProfileServerUpdate({
      draftDirty: true,
      draftBaseRevision: 8,
      nextServerRevision: 7,
      previousState: PROFILE_SERVER_UPDATE_NONE,
      now: NOW,
    });
    expect(state.status).toBe('none');
  });

  it('returns none for clean draft even with newer revision', () => {
    const state = detectProfileServerUpdate({
      draftDirty: false,
      draftBaseRevision: 8,
      nextServerRevision: 9,
      previousState: PROFILE_SERVER_UPDATE_NONE,
      now: NOW,
    });
    expect(state.status).toBe('none');
  });

  it('keeps original detectedAt when the same revision is detected again', () => {
    const previous: ProfileServerUpdateState = {
      status: 'detected',
      draftBaseRevision: 8,
      currentServerRevision: 9,
      detectedAt: NOW - 60_000,
    };
    const state = detectProfileServerUpdate({
      draftDirty: true,
      draftBaseRevision: 8,
      nextServerRevision: 9,
      previousState: previous,
      now: NOW,
    });
    expect(state).toBe(previous);
  });

  it('replaces detection when an even newer revision arrives', () => {
    const previous: ProfileServerUpdateState = {
      status: 'detected',
      draftBaseRevision: 8,
      currentServerRevision: 9,
      detectedAt: NOW - 60_000,
    };
    const state = detectProfileServerUpdate({
      draftDirty: true,
      draftBaseRevision: 8,
      nextServerRevision: 10,
      previousState: previous,
      now: NOW,
    });
    expect(state).toEqual({
      status: 'detected',
      draftBaseRevision: 8,
      currentServerRevision: 10,
      detectedAt: NOW,
    });
  });

  it('clears detection when the draft becomes clean', () => {
    const previous: ProfileServerUpdateState = {
      status: 'detected',
      draftBaseRevision: 8,
      currentServerRevision: 9,
      detectedAt: NOW - 60_000,
    };
    const state = detectProfileServerUpdate({
      draftDirty: false,
      draftBaseRevision: 9,
      nextServerRevision: 9,
      previousState: previous,
      now: NOW,
    });
    expect(state.status).toBe('none');
  });
});

describe('isNewServerUpdateDetection', () => {
  const detected: ProfileServerUpdateState = {
    status: 'detected',
    draftBaseRevision: 8,
    currentServerRevision: 9,
    detectedAt: NOW,
  };

  it('true when transitioning from none to detected', () => {
    expect(isNewServerUpdateDetection(PROFILE_SERVER_UPDATE_NONE, detected)).toBe(true);
  });

  it('false when the same revision stays detected', () => {
    expect(isNewServerUpdateDetection(detected, detected)).toBe(false);
  });

  it('true when a newer revision replaces the detection', () => {
    expect(
      isNewServerUpdateDetection(detected, {
        ...detected,
        currentServerRevision: 10,
      }),
    ).toBe(true);
  });

  it('false when next state is none', () => {
    expect(isNewServerUpdateDetection(detected, PROFILE_SERVER_UPDATE_NONE)).toBe(false);
  });
});
