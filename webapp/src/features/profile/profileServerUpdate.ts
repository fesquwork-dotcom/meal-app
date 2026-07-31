/**
 * Sprint 5.35 — early awareness of external server Profile updates.
 *
 * This state is a soft, client-side observation derived from GET refreshes.
 * It never replaces the server CAS (`PROFILE_STALE`) flow: the next PUT still
 * uses `expected_revision = draftBaseRevision` and the backend stays the
 * source of truth for concurrent saves.
 *
 * Lives only in the SPA session — never persisted to localStorage.
 */

export type ProfileServerUpdateState =
  | {
      status: 'none';
    }
  | {
      status: 'detected';
      draftBaseRevision: number;
      currentServerRevision: number;
      detectedAt: number;
    };

export const PROFILE_SERVER_UPDATE_NONE: ProfileServerUpdateState = { status: 'none' };

export type ProfileExternalUpdateSource =
  | 'memory_promotion'
  | 'behavior_recommendation'
  | 'learning_recommendation'
  | 'refresh'
  | 'conflict_resolution'
  /** Server-owned profile change inside the generation workflow (e.g. preview conflict resolution PUT). */
  | 'generation';

export interface ProfileServerUpdateDetectionInput {
  /** Local draft differs from the server profile. */
  draftDirty: boolean;
  /** Revision the draft was based on. */
  draftBaseRevision: number;
  /** Revision just received from the server. */
  nextServerRevision: number;
  previousState: ProfileServerUpdateState;
  now: number;
}

/**
 * Detection rule: `draft is dirty AND new server revision > draftBaseRevision`.
 * Comparing against the previous server revision alone is not enough — the
 * draft may already be based on the newest revision.
 */
export function detectProfileServerUpdate(
  input: ProfileServerUpdateDetectionInput,
): ProfileServerUpdateState {
  const { draftDirty, draftBaseRevision, nextServerRevision, previousState, now } = input;

  if (!draftDirty || nextServerRevision <= draftBaseRevision) {
    return PROFILE_SERVER_UPDATE_NONE;
  }

  if (
    previousState.status === 'detected' &&
    previousState.currentServerRevision === nextServerRevision &&
    previousState.draftBaseRevision === draftBaseRevision
  ) {
    // Same conflict already known — keep the original detection timestamp.
    return previousState;
  }

  return {
    status: 'detected',
    draftBaseRevision,
    currentServerRevision: nextServerRevision,
    detectedAt: now,
  };
}

export interface ExternalProfileUpdatePlanInput {
  source: ProfileExternalUpdateSource;
  draftDirty: boolean;
  draftBaseRevision: number;
  previousServerRevision: number;
  nextServerRevision: number;
  previousUpdateState: ProfileServerUpdateState;
  /** Last revision for which `external_profile_update` was already emitted. */
  alreadyNotifiedRevision: number | null;
  now: number;
}

export interface ExternalProfileUpdatePlan {
  /** Clean draft: replace the draft with the server version (no warning). */
  syncDraft: boolean;
  nextUpdateState: ProfileServerUpdateState;
  /**
   * Emit `external_profile_update` to the strategy-inputs coordinator.
   * Only background refresh does this; Memory promotion and Behavior
   * recommendation already emit their own single reason
   * (`memory_promoted` / `behavior_recommendation_applied`), conflict
   * resolution emits `profile_rebased`, and the generation workflow emits
   * its own reason (`conflict_resolved`). One operation → one reason.
   */
  notifyExternalProfileUpdate: boolean;
}

/** Central policy for applying a server-owned Profile update to the provider. */
export function planExternalProfileUpdate(
  input: ExternalProfileUpdatePlanInput,
): ExternalProfileUpdatePlan {
  const syncDraft = !input.draftDirty;

  const nextUpdateState = detectProfileServerUpdate({
    draftDirty: input.draftDirty,
    draftBaseRevision: input.draftBaseRevision,
    nextServerRevision: input.nextServerRevision,
    previousState: input.previousUpdateState,
    now: input.now,
  });

  const notifyExternalProfileUpdate =
    input.source === 'refresh' &&
    input.nextServerRevision > input.previousServerRevision &&
    input.alreadyNotifiedRevision !== input.nextServerRevision;

  return { syncDraft, nextUpdateState, notifyExternalProfileUpdate };
}

/** True when the state transitioned into a new detected revision (for logging). */
export function isNewServerUpdateDetection(
  previous: ProfileServerUpdateState,
  next: ProfileServerUpdateState,
): boolean {
  if (next.status !== 'detected') {
    return false;
  }
  return (
    previous.status !== 'detected' ||
    previous.currentServerRevision !== next.currentServerRevision
  );
}

/* Dev observability. Никогда не логируем значения Profile — только revision delta. */

export function logProfileServerUpdateDetected(
  state: Extract<ProfileServerUpdateState, { status: 'detected' }>,
  source: ProfileExternalUpdateSource,
): void {
  if (import.meta.env.DEV) {
    console.info('profile_server_update_detected', {
      revisionDelta: state.currentServerRevision - state.draftBaseRevision,
      source,
      draftDirty: true,
    });
  }
}

export function logProfileServerUpdateBannerDismissed(revision: number): void {
  if (import.meta.env.DEV) {
    console.info('profile_server_update_banner_dismissed', { revision });
  }
}

export function logProfileServerVersionLoaded(revision: number): void {
  if (import.meta.env.DEV) {
    console.info('profile_server_version_loaded', { revision });
  }
}

export function logProfileServerUpdateBecameConflict(
  state: Extract<ProfileServerUpdateState, { status: 'detected' }>,
): void {
  if (import.meta.env.DEV) {
    console.info('profile_server_update_became_conflict', {
      revisionDelta: state.currentServerRevision - state.draftBaseRevision,
      draftDirty: true,
    });
  }
}
