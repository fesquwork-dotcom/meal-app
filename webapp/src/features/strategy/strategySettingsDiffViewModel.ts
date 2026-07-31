import type { StrategySettingsDiff, StrategySettingChange } from '@/types/strategyCompare';

export interface StrategySettingsDiffViewModel {
  title: string;
  subtitle: string | null;
  changes: StrategySettingChange[];
  unchangedLine: string | null;
  noChanges: boolean;
  partialNotice: string | null;
  unavailable: boolean;
}

export function buildStrategySettingsDiffViewModel(
  diff: StrategySettingsDiff | null | undefined,
): StrategySettingsDiffViewModel | null {
  if (!diff) {
    return null;
  }

  if (diff.comparison_quality === 'unavailable') {
    return {
      title: 'Сравнение недоступно',
      subtitle: null,
      changes: [],
      unchangedLine: null,
      noChanges: false,
      partialNotice: null,
      unavailable: true,
    };
  }

  const partialNotice =
    diff.comparison_quality === 'partial'
      ? 'Для старого плана доступно частичное сравнение.'
      : null;

  if (!diff.has_changes) {
    return {
      title: 'Следующий план будет построен по тем же основным правилам.',
      subtitle: null,
      changes: [],
      unchangedLine: null,
      noChanges: true,
      partialNotice,
      unavailable: false,
    };
  }

  return {
    title: 'Что изменится в следующем плане',
    subtitle: null,
    changes: diff.changes,
    unchangedLine:
      diff.unchanged_count > 0
        ? `Остальные ${diff.unchanged_count} правил не изменятся.`
        : null,
    noChanges: false,
    partialNotice,
    unavailable: false,
  };
}

export function formatSettingChangeLine(change: StrategySettingChange): string {
  const current = change.current?.display_value;
  const next = change.next?.display_value;
  if (current && next && change.change_type !== 'source_changed') {
    return `${change.title}: ${current} → ${next}`;
  }
  return change.description;
}
