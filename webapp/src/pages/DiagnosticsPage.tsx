import { useCallback, useEffect, useState, type FC } from 'react';
import { Link } from 'react-router-dom';

import {
  getDevDiagnostics,
  loadQaScenario,
  resetCurrentDevUser,
  type DevDiagnosticsResult,
} from '@/api/devTools';
import { api } from '@/api/client';
import { Button, Card, CardContent, Section, Typography } from '@/components/ui';
import { clearClientStateAfterDevReset } from '@/features/diagnostics/clearClientStateAfterDevReset';
import { buildSafeDebugBundle } from '@/features/diagnostics/safeDebugBundle';
import { useMenuPlan } from '@/features/menu-plan/MenuPlanProvider';
import { useProfile } from '@/features/profile/ProfileProvider';
import { getRuntimeConfig } from '@/lib/runtimeConfig';
import {
  getTelegramInitData,
  getTelegramPlatform,
  getTelegramVersion,
  isTelegramEnvironment,
  isTelegramWebAppAvailable,
} from '@/lib/telegram';
import { ROUTES } from '@/constants/routes';

interface BackendHealth {
  status: string;
  version?: string;
  environment?: string;
  auth_mode: string;
  telegram_auth_configured?: boolean;
  dev_tools?: boolean;
  menu_generation_configured?: boolean;
}

interface BackendReady {
  status: string;
  database?: boolean;
  telegram_auth?: boolean;
  claude_configured?: boolean;
  components?: {
    database?: string;
    auth?: string;
    menu_generation?: string;
  };
}

const PHASE9_SCENARIOS = [
  'learning_candidate',
  'learned_preference_active',
  'learned_preference_insufficient',
  'learned_preference_emerging',
  'learned_preference_effective',
  'learned_preference_ineffective',
  'review_dismissed',
  'review_new_generation',
] as const;

function DiagnosticRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-4 border-b border-app-secondary py-2 last:border-0">
      <Typography variant="caption" className="text-app-hint">
        {label}
      </Typography>
      <Typography variant="body">{value}</Typography>
    </div>
  );
}

function readLastError(): { code: string | null; requestId: string | null } {
  try {
    const raw = sessionStorage.getItem('meal-planner:v1:last-safe-error');
    if (!raw) return { code: null, requestId: null };
    const parsed = JSON.parse(raw) as { code?: string; requestId?: string };
    return {
      code: typeof parsed.code === 'string' ? parsed.code : null,
      requestId:
        typeof parsed.requestId === 'string' ? parsed.requestId : null,
    };
  } catch {
    return { code: null, requestId: null };
  }
}

export const DiagnosticsPage: FC = () => {
  const runtime = getRuntimeConfig();
  const { isMenuPlanHydrated, menuPlan } = useMenuPlan();
  const { isProfileLoaded } = useProfile();
  const [health, setHealth] = useState<BackendHealth | null>(null);
  const [ready, setReady] = useState<BackendReady | null>(null);
  const [backendError, setBackendError] = useState<string | null>(null);
  const [devInfo, setDevInfo] = useState<DevDiagnosticsResult | null>(null);
  const [actionPending, setActionPending] = useState(false);
  const [actionMessage, setActionMessage] = useState<string | null>(null);
  const [copyStatus, setCopyStatus] = useState<string | null>(null);
  const lastError = readLastError();

  const refresh = useCallback(async () => {
    if (!runtime.apiBaseUrl) {
      setBackendError('API base URL is not configured');
      return;
    }
    try {
      const [healthResponse, readyResponse] = await Promise.all([
        api.get<BackendHealth>('/api/health'),
        api.get<BackendReady>('/api/ready'),
      ]);
      setHealth(healthResponse.data);
      setReady(readyResponse.data);
      setBackendError(null);
      if (healthResponse.data.dev_tools) {
        try {
          setDevInfo(await getDevDiagnostics());
        } catch {
          setDevInfo(null);
        }
      } else {
        setDevInfo(null);
      }
    } catch {
      setBackendError('Backend unreachable');
      setHealth(null);
      setReady(null);
      setDevInfo(null);
    }
  }, [runtime.apiBaseUrl]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const runReset = async (mode: 'history_only' | 'full_user') => {
    const label =
      mode === 'history_only'
        ? 'Сбросить тестовую историю? Profile сохранится.'
        : 'Полностью сбросить тестового пользователя? Profile тоже будет удалён.';
    if (!window.confirm(label)) return;
    setActionPending(true);
    setActionMessage(null);
    try {
      await resetCurrentDevUser(mode);
      clearClientStateAfterDevReset();
      setActionMessage(
        mode === 'history_only'
          ? 'История сброшена. Обновите страницу.'
          : 'Пользователь сброшен. Обновите страницу.',
      );
      await refresh();
    } catch {
      setActionMessage('Не удалось выполнить сброс. Данные не изменены.');
    } finally {
      setActionPending(false);
    }
  };

  const runScenario = async (scenario: string) => {
    setActionPending(true);
    setActionMessage(null);
    try {
      await loadQaScenario(scenario);
      clearClientStateAfterDevReset();
      setActionMessage(`Сценарий «${scenario}» загружен. Обновите страницу.`);
      await refresh();
    } catch {
      setActionMessage('Не удалось загрузить сценарий.');
    } finally {
      setActionPending(false);
    }
  };

  const copyBundle = async () => {
    const timezone =
      Intl.DateTimeFormat().resolvedOptions().timeZone || 'unknown';
    const bundle = buildSafeDebugBundle({
      appVersion: health?.version ?? 'unknown',
      frontendMode: runtime.isProduction ? 'production' : 'development',
      apiBaseUrl: runtime.apiBaseUrl,
      healthStatus: health?.status ?? backendError,
      readyStatus: ready?.status ?? null,
      authMode: health?.auth_mode ?? null,
      menuGeneration:
        ready?.components?.menu_generation ??
        (ready?.claude_configured ? 'ready' : 'not_configured'),
      telegramSdkAvailable: isTelegramWebAppAvailable(),
      telegramEnvironment: isTelegramEnvironment(),
      initDataPresent: Boolean(getTelegramInitData()),
      timezone,
      localeDate: new Date().toLocaleDateString(),
      networkOnline: typeof navigator !== 'undefined' ? navigator.onLine : true,
      route: '/diagnostics',
      lastErrorCode: lastError.code,
      lastRequestId: lastError.requestId,
      consistencyStatus: devInfo?.consistency.status ?? null,
      consistencyIssues: devInfo?.consistency.issues ?? [],
      lifecycleCounts: devInfo?.lifecycle_counts ?? null,
      devTools: Boolean(health?.dev_tools),
    });
    try {
      await navigator.clipboard.writeText(bundle);
      setCopyStatus('Скопировано');
    } catch {
      setCopyStatus('Не удалось скопировать');
    }
  };

  const showDevControls = Boolean(health?.dev_tools);

  return (
    <div className="flex flex-col gap-4 p-4 pb-8">
      <Section
        title="Diagnostics"
        description="Безопасная runtime-диагностика без секретов."
      />

      {showDevControls && (
        <Typography variant="caption" className="text-app-warning" role="status">
          Режим разработки
        </Typography>
      )}

      <Card>
        <CardContent className="pt-4">
          <DiagnosticRow
            label="Frontend mode"
            value={runtime.isProduction ? 'production' : 'development'}
          />
          <DiagnosticRow label="App version" value={health?.version ?? 'n/a'} />
          <DiagnosticRow
            label="Environment"
            value={health?.environment ?? 'n/a'}
          />
          <DiagnosticRow
            label="Timezone"
            value={Intl.DateTimeFormat().resolvedOptions().timeZone || 'n/a'}
          />
          <DiagnosticRow
            label="Browser date"
            value={new Date().toLocaleDateString()}
          />
          <DiagnosticRow
            label="Network"
            value={navigator.onLine ? 'online' : 'offline'}
          />
          <DiagnosticRow
            label="Telegram SDK available"
            value={isTelegramWebAppAvailable() ? 'yes' : 'no'}
          />
          <DiagnosticRow
            label="Telegram environment"
            value={isTelegramEnvironment() ? 'yes' : 'no'}
          />
          <DiagnosticRow
            label="initData present"
            value={getTelegramInitData() ? 'yes' : 'no'}
          />
          <DiagnosticRow
            label="Telegram platform"
            value={getTelegramPlatform() ?? 'n/a'}
          />
          <DiagnosticRow
            label="Telegram version"
            value={getTelegramVersion() ?? 'n/a'}
          />
          <DiagnosticRow
            label="API base URL"
            value={runtime.apiBaseUrl ?? 'not configured'}
          />
          <DiagnosticRow
            label="Backend health"
            value={health?.status ?? backendError ?? 'loading'}
          />
          <DiagnosticRow
            label="Backend auth_mode"
            value={health?.auth_mode ?? 'n/a'}
          />
          <DiagnosticRow label="Backend ready" value={ready?.status ?? 'n/a'} />
          <DiagnosticRow
            label="Menu generation"
            value={
              ready?.components?.menu_generation ??
              (ready?.claude_configured ? 'ready' : 'n/a')
            }
          />
          <DiagnosticRow
            label="Last error code"
            value={lastError.code ?? 'none'}
          />
          <DiagnosticRow
            label="Correlation ID"
            value={lastError.requestId ?? 'none'}
          />
          <DiagnosticRow
            label="Data consistency"
            value={
              devInfo
                ? `${devInfo.consistency.status}${
                    devInfo.consistency.issues.length
                      ? `: ${devInfo.consistency.issues.join(', ')}`
                      : ''
                  }`
                : showDevControls
                  ? 'loading'
                  : 'n/a'
            }
          />
          <DiagnosticRow
            label="menuPlan hydrated"
            value={isMenuPlanHydrated ? 'yes' : 'no'}
          />
          <DiagnosticRow
            label="menuPlan present"
            value={menuPlan ? 'yes' : 'no'}
          />
          <DiagnosticRow
            label="profile loaded"
            value={isProfileLoaded ? 'yes' : 'no'}
          />
        </CardContent>
      </Card>

      <Button
        type="button"
        variant="secondary"
        disabled={actionPending}
        onClick={() => void copyBundle()}
      >
        Скопировать диагностическую информацию
      </Button>
      {copyStatus && (
        <Typography variant="caption" className="text-app-hint" role="status">
          {copyStatus}
        </Typography>
      )}

      {showDevControls && (
        <>
          <Section
            title="QA tools"
            description="Только для локальной разработки. Недоступно в production."
          />
          <div className="flex flex-col gap-2">
            <Button
              type="button"
              variant="secondary"
              disabled={actionPending}
              onClick={() => void runReset('history_only')}
            >
              Сбросить тестовую историю
            </Button>
            <Button
              type="button"
              variant="secondary"
              disabled={actionPending}
              onClick={() => void runReset('full_user')}
            >
              Полностью сбросить тестового пользователя
            </Button>
          </div>
          <Typography variant="caption" className="text-app-hint">
            Phase 9 scenarios
          </Typography>
          <div className="flex flex-col gap-2">
            {PHASE9_SCENARIOS.map((scenario) => (
              <Button
                key={scenario}
                type="button"
                variant="secondary"
                disabled={actionPending}
                onClick={() => void runScenario(scenario)}
              >
                {scenario}
              </Button>
            ))}
          </div>
        </>
      )}

      {actionMessage && (
        <Typography variant="caption" className="text-app-hint" role="status">
          {actionMessage}
        </Typography>
      )}

      <Link to={ROUTES.HOME}>
        <Button type="button" variant="secondary" size="full">
          На главную
        </Button>
      </Link>
    </div>
  );
};
