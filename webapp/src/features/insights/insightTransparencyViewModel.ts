/**
 * Sprint 8.2 — transparency disclosure view model.
 * Pure presentation: normalizes already-computed backend texts into display
 * lines, никаких собственных вычислений и свободных строк.
 */

import { formatHistoryDate } from '@/features/menu-history/menuHistoryViewModel';
import type { Insight } from '@/types/insights';

export type TransparencyLineTone = 'ok' | 'warning' | 'neutral';

export interface TransparencyLineViewModel {
  id: string;
  tone: TransparencyLineTone;
  text: string;
}

export interface InsightTransparencyViewModel {
  toggleLabel: string;
  lines: TransparencyLineViewModel[];
}

const POSITIVE_EVENTS_LINE = 'Использованы подтверждённые события';

export function buildInsightTransparencyViewModel(
  insight: Insight,
): InsightTransparencyViewModel | null {
  const transparency = insight.transparency;
  if (!transparency) return null;

  const coverage = insight.evidence.coverage;
  const status = coverage?.status ?? 'insufficient';
  const lines: TransparencyLineViewModel[] = [];

  lines.push({
    id: 'proof',
    tone: status === 'insufficient' ? 'neutral' : 'ok',
    text: transparency.proof_text,
  });
  lines.push({
    id: 'coverage',
    tone: status === 'complete' ? 'ok' : status === 'partial' ? 'warning' : 'neutral',
    text: transparency.coverage_text,
  });

  if (insight.evidence.positive_events > 0) {
    lines.push({ id: 'positive-events', tone: 'ok', text: POSITIVE_EVENTS_LINE });
  }

  const newestLabel = formatHistoryDate(coverage?.newest_plan_date ?? null);
  if (newestLabel) {
    lines.push({
      id: 'newest-data',
      tone: 'ok',
      text: `Последние данные — ${newestLabel}`,
    });
  }

  if (transparency.availability_text) {
    lines.push({
      id: 'availability',
      tone: 'warning',
      text: transparency.availability_text,
    });
  }

  transparency.limitations_text.forEach((text, index) => {
    lines.push({ id: `limitation-${index}`, tone: 'warning', text });
  });

  return { toggleLabel: transparency.title, lines };
}
