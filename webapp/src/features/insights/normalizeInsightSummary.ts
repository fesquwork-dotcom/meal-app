import type {
  EvidenceCoverage,
  EvidenceCoverageStatus,
  Insight,
  InsightCategory,
  InsightConfidenceBasis,
  InsightConfidenceLevel,
  InsightEvidence,
  InsightEvidenceSource,
  InsightId,
  InsightLimitation,
  InsightStatus,
  InsightSummary,
  InsightTransparency,
  UnavailableReason,
} from '@/types/insights';

const INSIGHT_IDS = new Set<InsightId>([
  'replacement_health',
  'replacement_cost',
  'preference_stability',
  'recommendation_effectiveness',
  'positive_completion',
]);
const CATEGORIES = new Set<InsightCategory>([
  'progress',
  'consistency',
  'adaptation',
  'planning',
  'cost',
]);
const STATUSES = new Set<InsightStatus>([
  'insufficient_data',
  'informational',
  'confirmed',
]);
const LEVELS = new Set<InsightConfidenceLevel>(['low', 'medium', 'high']);
const BASES = new Set<InsightConfidenceBasis>(['trend', 'outcome', 'delta', 'none']);
const SOURCES = new Set<InsightEvidenceSource>([
  'trend.replacement_rate',
  'trend.decision_health',
  'trend.preference_stability',
  'trend.recommendation_effectiveness',
  'trend.positive_completion',
  'outcome.successful',
  'delta.total_cost',
]);
const COVERAGE_STATUSES = new Set<EvidenceCoverageStatus>([
  'insufficient',
  'partial',
  'complete',
]);
const LIMITATIONS = new Set<InsightLimitation>([
  'legacy_strategies',
  'positive_events_missing',
  'not_enough_completed_plans',
  'budget_data_unavailable',
  'menuplan_not_persisted',
  'decision_snapshot_missing',
  'outcome_snapshot_missing',
]);
const UNAVAILABLE_REASONS = new Set<UnavailableReason>([
  'need_more_completed_plans',
  'need_positive_events',
  'need_outcomes',
  'need_replacements',
  'metric_not_supported',
  'feature_not_available',
]);

function objectValue(value: unknown): Record<string, unknown> | null {
  return value != null && typeof value === 'object' && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
}

function safeText(value: unknown, limit: number): string | null {
  if (typeof value !== 'string') return null;
  const text = value.trim();
  if (!text || text.length > limit) return null;
  const internal =
    /\b(?:strategy_id|menu_plan_id|revision|decision_context|event_id|event_key|user_id)\b/i;
  return internal.test(text) ? null : text;
}

function nonNegativeInt(value: unknown): number {
  return typeof value === 'number' && Number.isInteger(value) && value >= 0
    ? value
    : 0;
}

function isoDate(value: unknown): string | null {
  return typeof value === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(value)
    ? value
    : null;
}

function allowlisted<T extends string>(value: unknown, allowed: Set<T>, max: number): T[] {
  if (!Array.isArray(value)) return [];
  return value
    .filter((item): item is T => typeof item === 'string' && allowed.has(item as T))
    .slice(0, max);
}

function normalizeCoverage(value: unknown): EvidenceCoverage | null {
  const coverage = objectValue(value);
  if (!coverage) return null;
  const status = coverage.status;
  if (typeof status !== 'string' || !COVERAGE_STATUSES.has(status as EvidenceCoverageStatus)) {
    return null;
  }
  return {
    status: status as EvidenceCoverageStatus,
    available_since: isoDate(coverage.available_since),
    oldest_plan_date: isoDate(coverage.oldest_plan_date),
    newest_plan_date: isoDate(coverage.newest_plan_date),
  };
}

function normalizeEvidence(
  evidence: Record<string, unknown>,
  sources: InsightEvidenceSource[],
): InsightEvidence {
  return {
    sources,
    evidence_weeks: nonNegativeInt(evidence.evidence_weeks),
    completed_strategies: nonNegativeInt(evidence.completed_strategies),
    positive_events: nonNegativeInt(evidence.positive_events),
    replacement_events: nonNegativeInt(evidence.replacement_events),
    decision_outcomes: nonNegativeInt(evidence.decision_outcomes),
    coverage: normalizeCoverage(evidence.coverage),
    limitations: allowlisted(evidence.limitations, LIMITATIONS, 7),
    unavailable_reasons: allowlisted(evidence.unavailable_reasons, UNAVAILABLE_REASONS, 6),
  };
}

function normalizeTransparency(value: unknown): InsightTransparency | null {
  const transparency = objectValue(value);
  if (!transparency) return null;
  const title = safeText(transparency.title, 80);
  const proof = safeText(transparency.proof_text, 200);
  const coverage = safeText(transparency.coverage_text, 200);
  if (!title || !proof || !coverage) return null;
  const limitations = Array.isArray(transparency.limitations_text)
    ? transparency.limitations_text
        .map((item) => safeText(item, 200))
        .filter((item): item is string => item !== null)
        .slice(0, 7)
    : [];
  return {
    title,
    proof_text: proof,
    coverage_text: coverage,
    availability_text: safeText(transparency.availability_text, 200),
    limitations_text: limitations,
  };
}

function normalizeInsight(value: unknown): Insight | null {
  const item = objectValue(value);
  const confidence = objectValue(item?.confidence);
  const evidence = objectValue(item?.evidence);
  if (!item || !confidence || !evidence) return null;

  const id = item.id;
  const category = item.category;
  const status = item.status;
  const level = confidence.level;
  const basis = confidence.basis;
  const title = safeText(item.title, 80);
  const summary = safeText(item.summary, 220);
  if (
    typeof id !== 'string' ||
    !INSIGHT_IDS.has(id as InsightId) ||
    typeof category !== 'string' ||
    !CATEGORIES.has(category as InsightCategory) ||
    typeof status !== 'string' ||
    !STATUSES.has(status as InsightStatus) ||
    typeof level !== 'string' ||
    !LEVELS.has(level as InsightConfidenceLevel) ||
    typeof basis !== 'string' ||
    !BASES.has(basis as InsightConfidenceBasis) ||
    !title ||
    !summary
  ) {
    return null;
  }
  const sources = Array.isArray(evidence.sources)
    ? evidence.sources
        .filter(
          (source): source is InsightEvidenceSource =>
            typeof source === 'string' && SOURCES.has(source as InsightEvidenceSource),
        )
        .slice(0, 5)
    : [];
  if (sources.length === 0) return null;

  return {
    id: id as InsightId,
    title,
    summary,
    category: category as InsightCategory,
    confidence: {
      level: level as InsightConfidenceLevel,
      basis: basis as InsightConfidenceBasis,
    },
    status: status as InsightStatus,
    evidence: normalizeEvidence(evidence, sources),
    available_since: safeText(item.available_since, 30) ?? 'sprint_8_1',
    transparency: normalizeTransparency(item.transparency),
  };
}

export function normalizeInsightSummary(value: unknown): InsightSummary | null {
  const payload = objectValue(value);
  if (!payload) return null;
  const generatedAt = safeText(payload.generated_at, 40);
  if (!generatedAt) return null;
  const insights = Array.isArray(payload.insights)
    ? payload.insights
        .map(normalizeInsight)
        .filter((item): item is Insight => item !== null)
        .slice(0, 10)
    : [];
  return {
    version:
      typeof payload.version === 'number' &&
      Number.isInteger(payload.version) &&
      payload.version >= 1
        ? payload.version
        : 1,
    generated_at: generatedAt,
    insights,
  };
}

