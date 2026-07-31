import type { MemorySignal, MemorySignalStatus } from '@/types/memory';

export interface MemorySignalViewModel {
  id: string;
  status: MemorySignalStatus;
  type: string;
  /** User-facing headline. Observed uses tentative wording, confirmed is assertive. */
  title: string;
  /** Optional supporting line (e.g. replacement count). */
  detail: string | null;
  /** True once the user has explicitly confirmed the signal. */
  isConfirmed: boolean;
  /** Confirmed avoid_ingredient signals can be promoted to profile preferences. */
  canPromote: boolean;
  /** Shown under confirmed avoid signals before promotion. */
  promotionHint: string | null;
}

const VALID_STATUSES: readonly MemorySignalStatus[] = ['observed', 'confirmed', 'dismissed'];

function isMemorySignal(value: unknown): value is MemorySignal {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    return false;
  }
  const raw = value as Record<string, unknown>;
  return (
    typeof raw.id === 'string' &&
    typeof raw.type === 'string' &&
    typeof raw.label === 'string' &&
    typeof raw.status === 'string' &&
    VALID_STATUSES.includes(raw.status as MemorySignalStatus) &&
    typeof raw.evidence_count === 'number' &&
    typeof raw.confidence === 'number'
  );
}

/** Safely parses the memory signals API response; unknown shapes yield an empty list. */
export function parseMemorySignals(input: unknown): MemorySignal[] {
  if (!input || typeof input !== 'object' || Array.isArray(input)) {
    return [];
  }
  const signals = (input as Record<string, unknown>).signals;
  if (!Array.isArray(signals)) {
    return [];
  }
  return signals.filter(isMemorySignal);
}

function describeAvoidIngredient(signal: MemorySignal): {
  title: string;
  detail: string | null;
  promotionHint: string | null;
} {
  const label = signal.label || 'этот продукт';
  if (signal.status === 'confirmed') {
    return {
      title: `Не предлагать ${label}`,
      detail: 'Запомнено по вашим заменам. Будет учитываться в следующих планах.',
      promotionHint:
        'После добавления продукт будет постоянно исключаться из следующих меню, пока вы не удалите его в профиле.',
    };
  }
  const detail =
    signal.evidence_count > 0
      ? `Замены: ${signal.evidence_count}. Подтвердите, чтобы учитывать в будущих планах`
      : 'Подтвердите, чтобы учитывать в будущих планах';
  return {
    title: `Возможно, вам не подходит ${label}`,
    detail,
    promotionHint: null,
  };
}

function describePreferFaster(signal: MemorySignal): {
  title: string;
  detail: string | null;
  promotionHint: string | null;
} {
  if (signal.status === 'confirmed') {
    return {
      title: 'Предпочитать более быстрые блюда',
      detail: 'Запомнено по вашим заменам. Будет учитываться в следующих планах.',
      promotionHint:
        'После добавления предпочтение станет постоянной настройкой профиля и будет применяться к следующим меню.',
    };
  }
  const base =
    signal.evidence_count > 0 ? `Замены: ${signal.evidence_count}` : null;
  const invitation = 'Подтвердите, чтобы учитывать в будущих планах';
  return {
    title: 'Вы несколько раз выбирали более быстрые блюда',
    detail: base ? `${base}. ${invitation}` : invitation,
    promotionHint: null,
  };
}

/** Builds user-safe wording for a single signal. Never surfaces raw codes or numbers as %. */
export function buildMemorySignalViewModel(signal: MemorySignal): MemorySignalViewModel {
  let described: { title: string; detail: string | null; promotionHint: string | null };
  switch (signal.type) {
    case 'avoid_ingredient':
      described = describeAvoidIngredient(signal);
      break;
    case 'prefer_faster_meals':
      described = describePreferFaster(signal);
      break;
    default:
      described = {
        title: signal.label || 'Приложение отметило предпочтение',
        detail: signal.evidence_count > 0 ? `Действий: ${signal.evidence_count}` : null,
        promotionHint: null,
      };
  }

  const canPromote =
    signal.status === 'confirmed' &&
    (signal.type === 'avoid_ingredient' || signal.type === 'prefer_faster_meals');

  return {
    id: signal.id,
    status: signal.status,
    type: signal.type,
    title: described.title,
    detail: described.detail,
    isConfirmed: signal.status === 'confirmed',
    canPromote,
    promotionHint: described.promotionHint,
  };
}

export function buildMemorySignalsViewModel(signals: MemorySignal[]): MemorySignalViewModel[] {
  return signals
    .filter((signal) => signal.status !== 'dismissed')
    .map(buildMemorySignalViewModel);
}
