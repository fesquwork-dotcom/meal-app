import type {
  DecisionExplanation,
  DecisionExplanationChange,
  DecisionExplanationCollection,
  DecisionExplanationSource,
} from '@/types/decisionExplanation';

const PUBLIC_KEYS = new Set([
  'budget.weekly',
  'cooking.time_limit',
  'cooking.prefer_faster',
  'cooking.cook_days',
  'cooking.batch_allowed',
  'shopping.days',
  'meal.leftovers_enabled',
  'meal.repeat_breakfasts',
  'meal.repeat_lunches',
  'meal.repeat_dinners',
  'protein.preferred',
  'protein.excluded',
  'exclusions.count',
  'behavior.availability_avoid_products',
  'planning.prefer_familiar_meals',
]);

const CONFIDENCE_LABELS = new Set([
  'Задано вами',
  'Рассчитано по правилам плана',
  'Учтено по подтверждённым предпочтениям',
  'Использовано стандартное значение',
]);

const CHANGE_TYPES = new Set(['value_changed', 'source_changed', 'rule_changed']);

function objectValue(value: unknown): Record<string, unknown> | null {
  return value != null && typeof value === 'object' && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
}

function cleanText(value: unknown, maxLength: number): string | null {
  if (typeof value !== 'string') return null;
  const cleaned = value.trim();
  const exposesTechnicalToken =
    /\b(?:rule_code|reason_code|input_summary|precedence|[A-Z]{3,}_[A-Z0-9_]+)\b/.test(cleaned);
  if (!cleaned || cleaned.length > maxLength || exposesTechnicalToken) return null;
  return cleaned;
}

function validKey(key: string, source: DecisionExplanationSource): boolean {
  return PUBLIC_KEYS.has(key) || (source === 'legacy' && /^legacy\.\d+$/.test(key));
}

function normalizeItem(
  value: unknown,
  source: DecisionExplanationSource,
): DecisionExplanation | null {
  const item = objectValue(value);
  if (!item) return null;
  const key = cleanText(item.decision_key, 80);
  const title = cleanText(item.title, 80);
  const outcome = cleanText(item.outcome, 160);
  const explanation = cleanText(item.explanation, 400);
  if (!key || !validKey(key, source) || !title || !outcome || !explanation) return null;

  const sourceLabel = item.source_label == null ? null : cleanText(item.source_label, 80);
  const alternative = item.alternative_note == null ? null : cleanText(item.alternative_note, 300);
  const confidence = item.confidence_label == null ? null : cleanText(item.confidence_label, 80);
  const supporting = Array.isArray(item.supporting_points)
    ? item.supporting_points
        .map((point) => cleanText(point, 200))
        .filter((point): point is string => point !== null)
        .slice(0, 4)
    : [];

  return {
    version: typeof item.version === 'number' ? item.version : 1,
    decision_key: key,
    title,
    outcome,
    explanation,
    source_label: sourceLabel,
    supporting_points: supporting,
    alternative_note: alternative,
    confidence_label: confidence && CONFIDENCE_LABELS.has(confidence) ? confidence : null,
  };
}

export function normalizeDecisionExplanations(
  value: unknown,
): DecisionExplanationCollection | null {
  const collection = objectValue(value);
  if (!collection || (collection.source !== 'trace' && collection.source !== 'legacy')) {
    return null;
  }
  const source = collection.source;
  const headline = cleanText(collection.headline, 120);
  const summary = cleanText(collection.summary, 400);
  if (!headline || !summary) return null;

  const explanations = Array.isArray(collection.explanations)
    ? collection.explanations
        .map((item) => normalizeItem(item, source))
        .filter((item): item is DecisionExplanation => item !== null)
        .slice(0, 8)
    : [];

  return {
    version: typeof collection.version === 'number' ? collection.version : 1,
    headline,
    summary,
    explanations,
    source,
  };
}

export function normalizeDecisionExplanationChanges(
  value: unknown,
): DecisionExplanationChange[] | null {
  if (value == null) return null;
  if (!Array.isArray(value)) return null;

  return value
    .map((raw): DecisionExplanationChange | null => {
      const item = objectValue(raw);
      if (!item) return null;
      const key = cleanText(item.decision_key, 80);
      const title = cleanText(item.title, 80);
      const before = cleanText(item.before, 160);
      const after = cleanText(item.after, 160);
      const explanation = cleanText(item.explanation, 300);
      const changeType = cleanText(item.change_type, 40);
      if (
        !key ||
        !PUBLIC_KEYS.has(key) ||
        !title ||
        !before ||
        !after ||
        !explanation ||
        !changeType ||
        !CHANGE_TYPES.has(changeType)
      ) {
        return null;
      }
      return {
        decision_key: key,
        title,
        before,
        after,
        explanation,
        change_type: changeType as DecisionExplanationChange['change_type'],
      };
    })
    .filter((item): item is DecisionExplanationChange => item !== null)
    .slice(0, 8);
}
