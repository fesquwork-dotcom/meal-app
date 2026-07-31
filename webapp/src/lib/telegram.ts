import { DEV_USER_ID } from '@/constants/development';
import { TELEGRAM_AUTH_SCHEME } from '@/constants/telegram';
import type { Profile } from '@/types/profile';
import type { TelegramUser, TelegramWebApp } from '@/types/telegram';

let telegramInitialized = false;

const THEME_PARAM_MAP: Record<string, string> = {
  bg_color: '--tg-theme-bg-color',
  text_color: '--tg-theme-text-color',
  hint_color: '--tg-theme-hint-color',
  link_color: '--tg-theme-link-color',
  button_color: '--tg-theme-button-color',
  button_text_color: '--tg-theme-button-text-color',
  secondary_bg_color: '--tg-theme-secondary-bg-color',
  header_bg_color: '--tg-theme-header-bg-color',
  accent_text_color: '--tg-theme-accent-text-color',
  section_bg_color: '--tg-theme-section-bg-color',
  section_header_text_color: '--tg-theme-section-header-text-color',
  subtitle_text_color: '--tg-theme-subtitle-text-color',
  destructive_text_color: '--tg-theme-destructive-text-color',
};

/** Returns Telegram WebApp instance when available. */
export function getTelegramWebApp(): TelegramWebApp | null {
  if (typeof window === 'undefined') {
    return null;
  }

  return window.Telegram?.WebApp ?? null;
}

/** Returns true when the app runs inside Telegram Mini App. */
export function isTelegramWebAppAvailable(): boolean {
  return getTelegramWebApp() !== null;
}

/** Returns true when Telegram environment is detected (WebApp present). */
export function isTelegramEnvironment(): boolean {
  return isTelegramWebAppAvailable();
}

/** Returns raw initData string from Telegram WebApp. Never cached or persisted. */
export function getTelegramInitData(): string | null {
  const initData = getTelegramWebApp()?.initData?.trim();
  return initData ? initData : null;
}

function applyTelegramTheme(webApp: TelegramWebApp): void {
  if (typeof document === 'undefined') {
    return;
  }

  const themeParams = webApp.themeParams;
  if (!themeParams) {
    return;
  }

  const root = document.documentElement;

  for (const [key, cssVar] of Object.entries(THEME_PARAM_MAP)) {
    const value = themeParams[key as keyof typeof themeParams];
    if (typeof value === 'string' && value) {
      root.style.setProperty(cssVar, value);
    }
  }

  root.dataset.telegramColorScheme = webApp.colorScheme;
}

function applyTelegramSafeArea(webApp: TelegramWebApp): void {
  if (typeof document === 'undefined') {
    return;
  }

  const inset = webApp.safeAreaInset ?? webApp.contentSafeAreaInset;
  if (!inset) {
    return;
  }

  const root = document.documentElement;
  root.style.setProperty('--tg-safe-area-top', `${inset.top}px`);
  root.style.setProperty('--tg-safe-area-bottom', `${inset.bottom}px`);
  root.style.setProperty('--tg-safe-area-left', `${inset.left}px`);
  root.style.setProperty('--tg-safe-area-right', `${inset.right}px`);
}

/** Initializes Telegram WebApp UI hooks. Safe to call in a regular browser. */
export function initializeTelegramWebApp(): void {
  if (telegramInitialized) {
    return;
  }

  const webApp = getTelegramWebApp();
  if (!webApp) {
    return;
  }

  try {
    webApp.ready?.();
    webApp.expand?.();
    applyTelegramTheme(webApp);
    applyTelegramSafeArea(webApp);
    telegramInitialized = true;
  } catch {
    // Ignore SDK errors on unsupported Telegram versions.
  }
}

export function getTelegramUser(): TelegramUser | null {
  const user = getTelegramWebApp()?.initDataUnsafe?.user;

  if (!user || typeof user.id !== 'number') {
    return null;
  }

  return user;
}

/**
 * UI/debug helper only. Server authorization uses verified initData — not this value.
 */
export function resolveUserId(): number {
  const telegramUser = getTelegramUser();

  if (telegramUser && Number.isInteger(telegramUser.id) && telegramUser.id > 0) {
    return telegramUser.id;
  }

  return DEV_USER_ID;
}

/** Display name: profile/draft first, then Telegram first_name fallback. */
export function getDisplayFirstName(profile: Profile | null): string {
  const profileName = profile?.first_name.trim();

  if (profileName) {
    return profileName;
  }

  const telegramName = getTelegramUser()?.first_name?.trim();

  if (telegramName) {
    return telegramName;
  }

  return '';
}

/** Builds Authorization header value for API requests. */
export function buildTelegramAuthorizationHeader(): string | null {
  const initData = getTelegramInitData();

  if (!initData) {
    return null;
  }

  return `${TELEGRAM_AUTH_SCHEME} ${initData}`;
}

export function getTelegramPlatform(): string | null {
  return getTelegramWebApp()?.platform ?? null;
}

export function getTelegramVersion(): string | null {
  return getTelegramWebApp()?.version ?? null;
}
