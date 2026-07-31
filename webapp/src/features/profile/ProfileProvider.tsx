import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type FC,
  type ReactNode,
} from 'react';
import { getProfile, ProfileStaleConflictError, saveProfile } from '@/api/profile';
import { STORAGE_KEYS } from '@/constants/storage';
import {
  createInitialAsyncResourceState,
  createResourceRequestController,
  getResourceRetryDescriptor,
  hasResourceData,
  isInitialLoading,
  isRefreshError,
  isRefreshing,
  isRequestAbortError,
  logResourceCacheHit,
  logResourceCacheStale,
  logResourceLoadFailed,
  logResourceLoadStarted,
  logResourceLoadSucceeded,
  logResourceResponseIgnored,
  RESOURCE_FRESHNESS_POLICIES,
  resourceError,
  selectResourceFreshness,
  shouldLoadResourceOnMount,
} from '@/features/async-resource';
import type { AsyncResourceState, ResourceRetryDescriptor } from '@/features/async-resource';
import { extractProfileStaleDetails } from '@/features/profile/extractProfileStaleDetails';
import {
  applyProfileDraft,
  areProfileSettingsEqual,
  extractProfileDraft,
  isProfileDraftDirty,
  normalizeProfileDraft,
} from '@/features/profile/profileDraft';
import {
  isNewServerUpdateDetection,
  logProfileServerUpdateBannerDismissed,
  logProfileServerUpdateBecameConflict,
  logProfileServerUpdateDetected,
  logProfileServerVersionLoaded,
  PROFILE_SERVER_UPDATE_NONE,
  planExternalProfileUpdate,
} from '@/features/profile/profileServerUpdate';
import type {
  ProfileExternalUpdateSource,
  ProfileServerUpdateState,
} from '@/features/profile/profileServerUpdate';
import { useStrategyInputs } from '@/features/strategy-inputs/useStrategyInputs';
import {
  classifyStrategyWorkflowError,
  logWorkflowErrorClassified,
} from '@/features/strategy-workflow';
import type {
  ProfileConflictState,
  ProfileReloadResult,
  SaveProfileResult,
  SaveProfileSuccess,
} from '@/features/strategy-workflow/workflowSuccessTypes';
import type { StrategyWorkflowError } from '@/features/strategy-workflow/types';
import { removeStorageItem, setStorageItem } from '@/lib/storage';
import { readVersionedStorage, wrapForStorage } from '@/lib/storageVersion';
import type { Profile } from '@/types/profile';

export type { ProfileConflictState };

export interface ProfileServerState {
  profile: Profile;
  revision: number;
  updatedAt: string | null;
}

const PROFILE_RESOURCE = 'profile';
const PROFILE_POLICY = RESOURCE_FRESHNESS_POLICIES.profile;

export interface ProfileContextValue {
  profile: Profile | null;
  serverProfile: Profile | null;
  serverRevision: number;
  draftBaseRevision: number;
  hasProfileDraft: boolean;
  updateProfile: (profile: Profile) => void;
  setProfile: (profile: Profile) => void;
  resetProfileDraft: () => void;
  saveProfileDraft: () => Promise<SaveProfileResult>;
  onProfileSaved: (profile: Profile, revision: number) => void;
  onGenerationSuccess: (profile: Profile) => void;
  conflict: ProfileConflictState | null;
  rebasePending: boolean;
  dismissConflict: () => void;
  /** Soft early warning: server profile changed while a dirty draft exists. */
  serverUpdate: ProfileServerUpdateState;
  /** Banner is hidden for this server revision after «Продолжить редактирование». */
  serverUpdateBannerDismissedForRevision: number | null;
  dismissServerUpdateBanner: () => void;
  /** «Загрузить сохранённые»: replace the draft with the server profile. */
  loadServerProfileVersion: () => void;
  /** Central entry point for server-owned profile updates (refresh, promotion, recommendation). */
  applyExternalProfileUpdate: (
    update: ProfileServerState,
    options: { source: ProfileExternalUpdateSource },
  ) => void;
  reloadServerProfile: () => ProfileReloadResult;
  beginRebaseOverwrite: () => void;
  cancelRebaseOverwrite: () => void;
  isProfileLoaded: boolean;
  isLoading: boolean;
  isRefreshing: boolean;
  isRefreshError: boolean;
  isSaving: boolean;
  /** Profile save/mutation error — separate from resource load error. */
  saveError: StrategyWorkflowError | null;
  /** Resource load/refresh error (typed). */
  error: StrategyWorkflowError | null;
  loadResource: AsyncResourceState<ProfileServerState>;
  retry: ResourceRetryDescriptor;
  reloadProfile: () => Promise<void>;
  /** Refresh only when stale (or empty). Safe for page remount. */
  ensureFreshProfile: () => Promise<void>;
}

const ProfileContext = createContext<ProfileContextValue | null>(null);

function loadProfileDraftFromStorage() {
  const stored = readVersionedStorage<unknown>(STORAGE_KEYS.PROFILE_DRAFT);
  return stored ? normalizeProfileDraft(stored) : null;
}

function toSaveSuccess(profile: Profile, revision: number): SaveProfileSuccess {
  return {
    profile,
    revision,
    updatedAt: profile.updated_at ?? null,
  };
}

export interface ProfileProviderProps {
  children: ReactNode;
}

export const ProfileProvider: FC<ProfileProviderProps> = ({ children }) => {
  const { notifyStrategyInputsChanged } = useStrategyInputs();
  const [serverProfile, setServerProfile] = useState<Profile | null>(null);
  const [serverRevision, setServerRevision] = useState(0);
  const [draftBaseRevision, setDraftBaseRevision] = useState(0);
  const [profile, setProfileState] = useState<Profile | null>(null);
  const [hasProfileDraft, setHasProfileDraft] = useState(false);
  const [conflict, setConflict] = useState<ProfileConflictState | null>(null);
  const [serverUpdate, setServerUpdate] = useState<ProfileServerUpdateState>(
    PROFILE_SERVER_UPDATE_NONE,
  );
  const [serverUpdateBannerDismissedForRevision, setServerUpdateBannerDismissedForRevision] =
    useState<number | null>(null);
  const [rebasePending, setRebasePending] = useState(false);
  const [isProfileLoaded, setIsProfileLoaded] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [saveError, setSaveError] = useState<StrategyWorkflowError | null>(null);
  const [loadResource, setLoadResource] = useState(
    () => createInitialAsyncResourceState<ProfileServerState>(),
  );
  const loadResourceRef = useRef(loadResource);
  loadResourceRef.current = loadResource;
  const hasProfileDraftRef = useRef(hasProfileDraft);
  hasProfileDraftRef.current = hasProfileDraft;
  const serverRevisionRef = useRef(serverRevision);
  serverRevisionRef.current = serverRevision;
  const draftBaseRevisionRef = useRef(draftBaseRevision);
  draftBaseRevisionRef.current = draftBaseRevision;
  const serverUpdateRef = useRef(serverUpdate);
  serverUpdateRef.current = serverUpdate;
  /** Last revision already announced to the coordinator as external_profile_update. */
  const notifiedExternalRevisionRef = useRef<number | null>(null);
  const requestControllerRef = useRef(createResourceRequestController());
  const hasFetchedRef = useRef(false);
  const rebasePendingRef = useRef(false);

  const clearServerUpdateState = useCallback(() => {
    setServerUpdate(PROFILE_SERVER_UPDATE_NONE);
    serverUpdateRef.current = PROFILE_SERVER_UPDATE_NONE;
    setServerUpdateBannerDismissedForRevision(null);
  }, []);

  const setServerUpdateState = useCallback((next: ProfileServerUpdateState) => {
    setServerUpdate(next);
    serverUpdateRef.current = next;
  }, []);

  const syncLoadedProfile = useCallback(
    (loaded: Profile, revision: number, draftBase: number) => {
      setServerProfile(loaded);
      setServerRevision(revision);
      serverRevisionRef.current = revision;
      setDraftBaseRevision(draftBase);
      draftBaseRevisionRef.current = draftBase;
      setProfileState(loaded);
      setHasProfileDraft(false);
      hasProfileDraftRef.current = false;
      setConflict(null);
      clearServerUpdateState();
      setRebasePending(false);
      rebasePendingRef.current = false;
      setSaveError(null);
      setIsProfileLoaded(true);
      const next: AsyncResourceState<ProfileServerState> = {
        status: 'ready',
        data: {
          profile: loaded,
          revision,
          updatedAt: loaded.updated_at ?? null,
        },
        error: null,
        lastUpdatedAt: Date.now(),
        requestId: loadResourceRef.current.requestId,
      };
      setLoadResource(next);
      loadResourceRef.current = next;
    },
    [clearServerUpdateState],
  );

  /** Initial hydrate only. Background refreshes go through applyExternalProfileUpdate. */
  const applyLoadedProfile = useCallback(
    (loaded: Profile, revision: number) => {
      const draft = loadProfileDraftFromStorage();

      if (draft && isProfileDraftDirty(loaded, draft)) {
        setServerProfile(loaded);
        setServerRevision(revision);
        serverRevisionRef.current = revision;
        setDraftBaseRevision(revision);
        draftBaseRevisionRef.current = revision;
        setProfileState(applyProfileDraft(loaded, draft));
        setHasProfileDraft(true);
        hasProfileDraftRef.current = true;
        setConflict(null);
        setRebasePending(false);
        rebasePendingRef.current = false;
        setIsProfileLoaded(true);
        const next: AsyncResourceState<ProfileServerState> = {
          status: 'ready',
          data: {
            profile: loaded,
            revision,
            updatedAt: loaded.updated_at ?? null,
          },
          error: null,
          lastUpdatedAt: Date.now(),
          requestId: loadResourceRef.current.requestId,
        };
        setLoadResource(next);
        loadResourceRef.current = next;
        return;
      }

      if (draft) {
        removeStorageItem(STORAGE_KEYS.PROFILE_DRAFT);
      }

      syncLoadedProfile(loaded, revision, revision);
    },
    [syncLoadedProfile],
  );

  /**
   * Central handler for server-owned profile updates (background refresh,
   * Memory promotion, Behavior recommendation, conflict resolution).
   * Clean draft → full sync without warning. Dirty draft → server snapshot
   * only; draft, draftBaseRevision and dirty flag are preserved and a soft
   * server-update warning is detected. Never rebases silently.
   */
  const applyExternalProfileUpdate = useCallback(
    (update: ProfileServerState, options: { source: ProfileExternalUpdateSource }) => {
      const previousUpdateState = serverUpdateRef.current;
      const plan = planExternalProfileUpdate({
        source: options.source,
        draftDirty: hasProfileDraftRef.current,
        draftBaseRevision: draftBaseRevisionRef.current,
        previousServerRevision: serverRevisionRef.current,
        nextServerRevision: update.revision,
        previousUpdateState,
        alreadyNotifiedRevision: notifiedExternalRevisionRef.current,
        now: Date.now(),
      });

      if (plan.syncDraft) {
        syncLoadedProfile(update.profile, update.revision, update.revision);
      } else {
        setServerProfile(update.profile);
        setServerRevision(update.revision);
        serverRevisionRef.current = update.revision;
        setIsProfileLoaded(true);
        const next: AsyncResourceState<ProfileServerState> = {
          status: 'ready',
          data: update,
          error: null,
          lastUpdatedAt: Date.now(),
          requestId: loadResourceRef.current.requestId,
        };
        setLoadResource(next);
        loadResourceRef.current = next;
        if (
          plan.nextUpdateState.status === 'detected' &&
          isNewServerUpdateDetection(previousUpdateState, plan.nextUpdateState)
        ) {
          logProfileServerUpdateDetected(plan.nextUpdateState, options.source);
        }
        setServerUpdateState(plan.nextUpdateState);
      }

      if (plan.notifyExternalProfileUpdate) {
        notifiedExternalRevisionRef.current = update.revision;
        notifyStrategyInputsChanged('external_profile_update');
      }
    },
    [syncLoadedProfile, setServerUpdateState, notifyStrategyInputsChanged],
  );

  const reloadProfile = useCallback(async () => {
    const hadPrevious = loadResourceRef.current.data !== null;
    const { requestId, signal } = requestControllerRef.current.begin('superseded');
    const loadingState: AsyncResourceState<ProfileServerState> = hadPrevious
      ? {
          status: 'refreshing',
          data: loadResourceRef.current.data as ProfileServerState,
          error: null,
          lastUpdatedAt: loadResourceRef.current.lastUpdatedAt ?? Date.now(),
          requestId,
        }
      : {
          status: 'loading',
          data: null,
          error: null,
          lastUpdatedAt: null,
          requestId,
        };
    setLoadResource(loadingState);
    loadResourceRef.current = loadingState;
    logResourceLoadStarted(PROFILE_RESOURCE, requestId);

    try {
      const loaded = await getProfile({ signal });
      if (
        !requestControllerRef.current.isCurrent(requestId) ||
        loadResourceRef.current.requestId !== requestId
      ) {
        logResourceResponseIgnored(PROFILE_RESOURCE, requestId, loadResourceRef.current.requestId);
        return;
      }
      const serverState: ProfileServerState = {
        profile: loaded.profile,
        revision: loaded.revision,
        updatedAt: loaded.profile.updated_at ?? null,
      };
      if (
        hadPrevious &&
        loadResourceRef.current.data &&
        loadResourceRef.current.data.revision > serverState.revision
      ) {
        logResourceResponseIgnored(PROFILE_RESOURCE, requestId, loadResourceRef.current.requestId);
        return;
      }
      if (hadPrevious) {
        applyExternalProfileUpdate(serverState, { source: 'refresh' });
      } else {
        applyLoadedProfile(loaded.profile, loaded.revision);
      }
      setIsProfileLoaded(true);
      const next: AsyncResourceState<ProfileServerState> = {
        status: 'ready',
        data: serverState,
        error: null,
        lastUpdatedAt: Date.now(),
        requestId,
      };
      setLoadResource(next);
      loadResourceRef.current = next;
      logResourceLoadSucceeded(PROFILE_RESOURCE, requestId);
    } catch (err: unknown) {
      if (isRequestAbortError(err)) {
        return;
      }
      if (
        !requestControllerRef.current.isCurrent(requestId) ||
        loadResourceRef.current.requestId !== requestId
      ) {
        logResourceResponseIgnored(PROFILE_RESOURCE, requestId, loadResourceRef.current.requestId);
        return;
      }
      const workflowError = classifyStrategyWorkflowError(err);
      if (!hadPrevious) {
        setIsProfileLoaded(false);
      }
      const next: AsyncResourceState<ProfileServerState> = {
        status: 'error',
        data: hadPrevious ? loadResourceRef.current.data : null,
        error: workflowError,
        lastUpdatedAt: hadPrevious ? loadResourceRef.current.lastUpdatedAt : null,
        requestId,
      };
      setLoadResource(next);
      loadResourceRef.current = next;
      logResourceLoadFailed(PROFILE_RESOURCE, requestId, workflowError, hadPrevious);
    }
  }, [applyLoadedProfile, applyExternalProfileUpdate]);

  const ensureFreshProfile = useCallback(async () => {
    const now = Date.now();
    const current = loadResourceRef.current;
    const freshness = selectResourceFreshness(current, PROFILE_POLICY, now);
    if (!shouldLoadResourceOnMount(current, PROFILE_POLICY, now)) {
      logResourceCacheHit(PROFILE_RESOURCE, freshness);
      return;
    }
    if (hasResourceData(current) && freshness === 'stale') {
      logResourceCacheStale(PROFILE_RESOURCE, freshness);
    }
    await reloadProfile();
  }, [reloadProfile]);
  useEffect(() => {
    if (hasFetchedRef.current) {
      return;
    }

    hasFetchedRef.current = true;
    void reloadProfile();
  }, [reloadProfile]);

  const persistDraftIfNeeded = useCallback(
    (next: Profile, base: Profile) => {
      const draft = extractProfileDraft(next);

      if (isProfileDraftDirty(base, draft)) {
        setStorageItem(STORAGE_KEYS.PROFILE_DRAFT, wrapForStorage(draft));
        setHasProfileDraft(true);
        hasProfileDraftRef.current = true;
        return;
      }

      removeStorageItem(STORAGE_KEYS.PROFILE_DRAFT);
      setHasProfileDraft(false);
      hasProfileDraftRef.current = false;
      // Draft is clean again — the soft server-update warning no longer applies.
      clearServerUpdateState();
    },
    [clearServerUpdateState],
  );

  const updateProfile = useCallback(
    (next: Profile) => {
      setProfileState(next);
      setSaveError(null);

      if (!serverProfile) {
        return;
      }

      persistDraftIfNeeded(next, serverProfile);
    },
    [serverProfile, persistDraftIfNeeded],
  );

  const setProfile = useCallback(
    (next: Profile) => {
      updateProfile(next);
    },
    [updateProfile],
  );

  const resetProfileDraft = useCallback(() => {
    removeStorageItem(STORAGE_KEYS.PROFILE_DRAFT);
    setHasProfileDraft(false);
    hasProfileDraftRef.current = false;
    setRebasePending(false);
    rebasePendingRef.current = false;
    setConflict(null);
    clearServerUpdateState();

    if (serverProfile) {
      setProfileState(serverProfile);
      setDraftBaseRevision(serverRevision);
      draftBaseRevisionRef.current = serverRevision;
    }
  }, [serverProfile, serverRevision, clearServerUpdateState]);

  const onProfileSaved = useCallback(
    (savedProfile: Profile, revision: number) => {
      removeStorageItem(STORAGE_KEYS.PROFILE_DRAFT);
      syncLoadedProfile(savedProfile, revision, revision);
    },
    [syncLoadedProfile],
  );

  /** «Продолжить редактирование»: hide the banner for the current server revision only. */
  const dismissServerUpdateBanner = useCallback(() => {
    const current = serverUpdateRef.current;
    if (current.status !== 'detected') {
      return;
    }
    setServerUpdateBannerDismissedForRevision(current.currentServerRevision);
    logProfileServerUpdateBannerDismissed(current.currentServerRevision);
  }, []);

  /**
   * «Загрузить сохранённые»: explicit user action that replaces the draft
   * with the server profile and rebases draftBaseRevision to the server
   * revision. Invalidates preview/compare via `profile_rebased`; the local
   * MenuPlan is never touched.
   */
  const loadServerProfileVersion = useCallback(() => {
    if (!serverProfile) {
      return;
    }
    removeStorageItem(STORAGE_KEYS.PROFILE_DRAFT);
    syncLoadedProfile(serverProfile, serverRevision, serverRevision);
    notifyStrategyInputsChanged('profile_rebased');
    logProfileServerVersionLoaded(serverRevision);
  }, [serverProfile, serverRevision, syncLoadedProfile, notifyStrategyInputsChanged]);

  const saveProfileDraft = useCallback(async (): Promise<SaveProfileResult> => {
    if (!profile) {
      const error = classifyStrategyWorkflowError(new Error('Профиль не загружен'));
      setSaveError(error);
      return { ok: false, error };
    }

    const draft = extractProfileDraft(profile);
    if (conflict && areProfileSettingsEqual(conflict.details.currentProfile, draft)) {
      onProfileSaved(conflict.details.currentProfile, conflict.details.currentRevision);
      return {
        ok: true,
        data: toSaveSuccess(conflict.details.currentProfile, conflict.details.currentRevision),
      };
    }

    setIsSaving(true);
    setSaveError(null);

    try {
      const saved = await saveProfile(profile, draftBaseRevision);
      const wasRebase = rebasePendingRef.current;
      onProfileSaved(saved.profile, saved.revision);
      notifyStrategyInputsChanged(wasRebase ? 'profile_rebased' : 'profile_saved');
      if (import.meta.env.DEV) {
        console.info('workflow_action_succeeded', {
          domain: 'profile',
          action: wasRebase ? 'rebase_save' : 'save',
        });
      }
      return { ok: true, data: toSaveSuccess(saved.profile, saved.revision) };
    } catch (err: unknown) {
      if (err instanceof ProfileStaleConflictError) {
        const draftAfterConflict = extractProfileDraft(profile);
        if (areProfileSettingsEqual(err.currentProfile, draftAfterConflict)) {
          onProfileSaved(err.currentProfile, err.currentRevision);
          return { ok: true, data: toSaveSuccess(err.currentProfile, err.currentRevision) };
        }
        const details = extractProfileStaleDetails(err);
        const workflowError = classifyStrategyWorkflowError(err);
        logWorkflowErrorClassified(workflowError);
        if (serverUpdateRef.current.status === 'detected') {
          logProfileServerUpdateBecameConflict(serverUpdateRef.current);
        }
        if (details) {
          setConflict({ error: workflowError, details });
        }
        setRebasePending(false);
        rebasePendingRef.current = false;
        setSaveError(null);
        if (import.meta.env.DEV) {
          console.info('profile_workflow_failed', {
            domain: 'profile',
            action: 'save',
            kind: workflowError.kind,
            code: workflowError.code,
            status: workflowError.originalStatus,
          });
        }
        return { ok: false, error: workflowError };
      }
      const workflowError = classifyStrategyWorkflowError(err);
      logWorkflowErrorClassified(workflowError);
      setSaveError(workflowError);
      if (import.meta.env.DEV) {
        console.info('profile_workflow_failed', {
          domain: 'profile',
          action: 'save',
          kind: workflowError.kind,
          code: workflowError.code,
          status: workflowError.originalStatus,
        });
      }
      return { ok: false, error: workflowError };
    } finally {
      setIsSaving(false);
    }
  }, [profile, conflict, draftBaseRevision, onProfileSaved, notifyStrategyInputsChanged]);

  const dismissConflict = useCallback(() => {
    setConflict(null);
    setRebasePending(false);
    rebasePendingRef.current = false;
  }, []);

  const reloadServerProfile = useCallback((): ProfileReloadResult => {
    if (!conflict) {
      const error = classifyStrategyWorkflowError(new Error('Нет конфликта профиля'));
      return { ok: false, error };
    }
    onProfileSaved(conflict.details.currentProfile, conflict.details.currentRevision);
    notifyStrategyInputsChanged('profile_rebased');
    return {
      ok: true,
      data: {
        profile: conflict.details.currentProfile,
        revision: conflict.details.currentRevision,
      },
    };
  }, [conflict, onProfileSaved, notifyStrategyInputsChanged]);

  const beginRebaseOverwrite = useCallback(() => {
    if (!conflict) {
      return;
    }
    setDraftBaseRevision(conflict.details.currentRevision);
    setRebasePending(true);
    rebasePendingRef.current = true;
  }, [conflict]);

  const cancelRebaseOverwrite = useCallback(() => {
    setRebasePending(false);
    rebasePendingRef.current = false;
  }, []);

  const onGenerationSuccess = useCallback(
    (savedProfile: Profile) => {
      // Generation applied the settings server-side and the draft storage was
      // already cleared; reset the dirty flag so the follow-up refresh takes
      // the clean-sync path instead of raising a server-update warning.
      setHasProfileDraft(false);
      hasProfileDraftRef.current = false;
      clearServerUpdateState();
      void reloadProfile();
      setProfileState(savedProfile);
    },
    [reloadProfile, clearServerUpdateState],
  );

  const loadError = resourceError(loadResource);
  const isLoading = isInitialLoading(loadResource) && !hasResourceData(loadResource);
  const refreshPending = isRefreshing(loadResource);
  const refreshFailed = isRefreshError(loadResource);
  const retry = getResourceRetryDescriptor(loadResource);

  const value = useMemo<ProfileContextValue>(
    () => ({
      profile,
      serverProfile,
      serverRevision,
      draftBaseRevision,
      hasProfileDraft,
      updateProfile,
      setProfile,
      resetProfileDraft,
      saveProfileDraft,
      onProfileSaved,
      onGenerationSuccess,
      conflict,
      rebasePending,
      dismissConflict,
      serverUpdate,
      serverUpdateBannerDismissedForRevision,
      dismissServerUpdateBanner,
      loadServerProfileVersion,
      applyExternalProfileUpdate,
      reloadServerProfile,
      beginRebaseOverwrite,
      cancelRebaseOverwrite,
      isProfileLoaded: isProfileLoaded || hasResourceData(loadResource),
      isLoading,
      isRefreshing: refreshPending,
      isRefreshError: refreshFailed,
      isSaving,
      saveError,
      error: loadError,
      loadResource,
      retry,
      reloadProfile,
      ensureFreshProfile,
    }),
    [
      profile,
      serverProfile,
      serverRevision,
      draftBaseRevision,
      hasProfileDraft,
      updateProfile,
      setProfile,
      resetProfileDraft,
      saveProfileDraft,
      onProfileSaved,
      onGenerationSuccess,
      conflict,
      rebasePending,
      dismissConflict,
      serverUpdate,
      serverUpdateBannerDismissedForRevision,
      dismissServerUpdateBanner,
      loadServerProfileVersion,
      applyExternalProfileUpdate,
      reloadServerProfile,
      beginRebaseOverwrite,
      cancelRebaseOverwrite,
      isProfileLoaded,
      loadResource,
      isLoading,
      refreshPending,
      refreshFailed,
      isSaving,
      saveError,
      loadError,
      retry,
      reloadProfile,
      ensureFreshProfile,
    ],
  );

  return <ProfileContext.Provider value={value}>{children}</ProfileContext.Provider>;
};

export function useProfile(): ProfileContextValue {
  const context = useContext(ProfileContext);

  if (!context) {
    throw new Error('useProfile must be used within ProfileProvider');
  }

  return context;
}
