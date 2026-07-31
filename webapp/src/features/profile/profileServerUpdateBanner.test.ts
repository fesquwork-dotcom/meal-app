import { describe, expect, it } from 'vitest';

import bannerSource from '@/features/profile/ProfileServerUpdateBanner.tsx?raw';
import profilePageSource from '@/pages/ProfilePage.tsx?raw';

describe('ProfileServerUpdateBanner (source smoke)', () => {
  it('uses non-critical status semantics for accessibility', () => {
    expect(bannerSource).toContain('role="status"');
    expect(bannerSource).toContain('aria-live="polite"');
    expect(bannerSource).not.toContain('role="alert"');
  });

  it('offers both explicit text actions', () => {
    expect(bannerSource).toContain('Продолжить редактирование');
    expect(bannerSource).toContain('Загрузить сохранённые');
  });

  it('renders through the pure view model instead of inline JSX conditions', () => {
    expect(bannerSource).toContain('buildProfileServerUpdateViewModel');
    expect(bannerSource).toContain('if (!viewModel.visible)');
  });

  it('uses theme tokens instead of destructive styling', () => {
    expect(bannerSource).toContain('bg-app-secondary');
    expect(bannerSource).not.toContain('variant="destructive"');
    expect(bannerSource).not.toContain('bg-app-destructive');
  });

  it('does not persist anything to localStorage', () => {
    expect(bannerSource).not.toContain('localStorage');
    expect(bannerSource).not.toContain('setStorageItem');
  });
});

describe('ProfilePage banner integration (source smoke)', () => {
  it('renders the banner with dismissal semantics and both handlers', () => {
    expect(profilePageSource).toContain('ProfileServerUpdateBanner');
    expect(profilePageSource).toContain('dismissedForRevision={serverUpdateBannerDismissedForRevision}');
    expect(profilePageSource).toContain('onContinueEditing={dismissServerUpdateBanner}');
    expect(profilePageSource).toContain('onLoadServerVersion={handleLoadServerVersion}');
  });

  it('hides the banner while the PROFILE_STALE conflict dialog is active', () => {
    expect(profilePageSource).toContain('{!conflict && (');
    expect(profilePageSource).toContain('ProfileConflictDialog');
  });

  it('announces the loaded server version and returns focus to the heading', () => {
    expect(profilePageSource).toContain('Загружена сохранённая версия настроек.');
    expect(profilePageSource).toContain('settingsHeadingRef.current?.focus()');
  });

  it('save button is not blocked by the soft warning', () => {
    expect(profilePageSource).not.toContain('serverUpdate.status === \'detected\' ||');
    expect(profilePageSource).toContain(
      'disabled={(!hasProfileDraft && !rebasePending) || isSaving || isLoading || Boolean(conflict && !rebasePending)}',
    );
  });
});
