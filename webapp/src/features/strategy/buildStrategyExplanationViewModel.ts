import type { StrategyExplanation, StrategyReason } from '@/types/strategy';

export const MAX_VISIBLE_REASONS = 5;

export interface StrategyExplanationViewModel {
  headline: string;
  summary: string;
  reasons: StrategyReason[];
  hasExplanation: boolean;
}

function isStrategyReason(value: unknown): value is StrategyReason {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    return false;
  }

  const raw = value as Record<string, unknown>;
  return (
    typeof raw.code === 'string' &&
    typeof raw.title === 'string' &&
    typeof raw.description === 'string' &&
    typeof raw.category === 'string' &&
    typeof raw.priority === 'number'
  );
}

export function parseStrategyExplanation(input: unknown): StrategyExplanation | null {
  if (!input || typeof input !== 'object' || Array.isArray(input)) {
    return null;
  }

  const raw = input as Record<string, unknown>;
  if (
    typeof raw.version !== 'number' ||
    typeof raw.headline !== 'string' ||
    typeof raw.summary !== 'string' ||
    !Array.isArray(raw.reasons)
  ) {
    return null;
  }

  const reasons = raw.reasons.filter(isStrategyReason);
  const source = raw.source === 'recorded' || raw.source === 'inferred' ? raw.source : 'inferred';

  return {
    version: raw.version,
    source,
    headline: raw.headline,
    summary: raw.summary,
    reasons,
  };
}

export function buildStrategyExplanationViewModel(
  explanation: StrategyExplanation | null | undefined,
): StrategyExplanationViewModel | null {
  if (!explanation) {
    return null;
  }

  const sortedReasons = [...explanation.reasons].sort(
    (left, right) => left.priority - right.priority || left.code.localeCompare(right.code),
  );

  return {
    headline: explanation.headline,
    summary: explanation.summary,
    reasons: sortedReasons.slice(0, MAX_VISIBLE_REASONS),
    hasExplanation: true,
  };
}
