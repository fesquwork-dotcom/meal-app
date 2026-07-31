import { useEffect, useState, type FC, type ReactNode } from 'react';
import { api } from '@/api/client';
import { Typography } from '@/components/ui';
import { getRuntimeConfig } from '@/lib/runtimeConfig';
import {
  getTelegramInitData,
  getTelegramWebApp,
  isTelegramEnvironment,
  isTelegramWebAppAvailable,
} from '@/lib/telegram';

interface BackendHealth {
  auth_mode: 'telegram' | 'development';
}

interface AppBootstrapProps {
  children: ReactNode;
}

const ConfigurationErrorScreen: FC<{ message: string }> = ({ message }) => (
  <div className="flex min-h-screen items-center justify-center bg-app-bg p-6">
    <div className="max-w-md text-center">
      <Typography variant="h2">Ошибка конфигурации</Typography>
      <Typography variant="body" className="mt-3 text-app-hint">
        {message}
      </Typography>
    </div>
  </div>
);

const TelegramOnlyScreen: FC = () => (
  <div className="flex min-h-screen items-center justify-center bg-app-bg p-6">
    <div className="max-w-md text-center">
      <Typography variant="h2">Откройте приложение через Telegram-бота</Typography>
      <Typography variant="body" className="mt-3 text-app-hint">
        Эта production-версия работает только внутри Telegram Mini App.
      </Typography>
    </div>
  </div>
);

export const AppBootstrap: FC<AppBootstrapProps> = ({ children }) => {
  const runtime = getRuntimeConfig();
  const [gateState, setGateState] = useState<'loading' | 'ready' | 'telegram-only'>('loading');

  useEffect(() => {
    let cancelled = false;

    async function evaluateTelegramGate() {
      if (!runtime.isProduction || runtime.configError) {
        setGateState('ready');
        return;
      }

      if (!runtime.apiBaseUrl) {
        setGateState('ready');
        return;
      }

      try {
        const { data } = await api.get<BackendHealth>('/api/health');

        if (cancelled) {
          return;
        }

        const requiresTelegram = data.auth_mode === 'telegram';
        const hasTelegramContext =
          isTelegramWebAppAvailable() && isTelegramEnvironment() && Boolean(getTelegramInitData());

        if (requiresTelegram && !hasTelegramContext) {
          setGateState('telegram-only');
          return;
        }

        setGateState('ready');
      } catch {
        if (!cancelled) {
          setGateState('ready');
        }
      }
    }

    void evaluateTelegramGate();

    return () => {
      cancelled = true;
    };
  }, [runtime.apiBaseUrl, runtime.configError, runtime.isProduction]);

  if (runtime.isProduction && runtime.configError) {
    return <ConfigurationErrorScreen message={runtime.configError} />;
  }

  if (gateState === 'loading') {
    return (
      <div className="flex min-h-screen items-center justify-center bg-app-bg p-6" aria-busy="true">
        <span className="sr-only">Проверяем окружение приложения…</span>
        <Typography variant="body" className="text-app-hint">
          Загружаем приложение…
        </Typography>
      </div>
    );
  }

  if (gateState === 'telegram-only') {
    return <TelegramOnlyScreen />;
  }

  const webApp = getTelegramWebApp();
  if (webApp && typeof document !== 'undefined') {
    document.documentElement.style.setProperty(
      '--tg-safe-area-top',
      `${webApp.safeAreaInset?.top ?? 0}px`,
    );
    document.documentElement.style.setProperty(
      '--tg-safe-area-bottom',
      `${webApp.safeAreaInset?.bottom ?? 0}px`,
    );
  }

  return children;
};
