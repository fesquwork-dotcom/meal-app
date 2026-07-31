import type {
  DietaryConstraint,
  DietaryConstraintInput,
  DietaryConstraintKind,
  ProfileApiRecord,
} from '@/types/profile';

const CONSTRAINT_KINDS: DietaryConstraintKind[] = ['allergy', 'intolerance', 'preference'];

function isConstraintKind(value: string): value is DietaryConstraintKind {
  return (CONSTRAINT_KINDS as string[]).includes(value);
}

function safeString(value: unknown): string {
  return typeof value === 'string' ? value.trim() : '';
}

/** Normalizes dietary constraints from API or draft input. */
export function normalizeDietaryConstraints(raw: unknown): DietaryConstraint[] {
  if (!Array.isArray(raw)) {
    return [];
  }

  const indexByValue = new Map<string, number>();
  const result: DietaryConstraint[] = [];

  for (const entry of raw) {
    if (!entry || typeof entry !== 'object' || Array.isArray(entry)) {
      continue;
    }
    const record = entry as Record<string, unknown>;
    const rawKind = safeString(record.kind);
    const value = safeString(record.value);
    if (!value || !isConstraintKind(rawKind)) {
      continue;
    }
    // Legacy intolerance remains readable but is projected into the single
    // safety section. New UI and save payloads never create intolerance.
    const kind: DietaryConstraintKind = rawKind === 'intolerance' ? 'allergy' : rawKind;
    const dedupeKey = value.toLowerCase();
    const existingIndex = indexByValue.get(dedupeKey);
    if (existingIndex !== undefined) {
      if (kind === 'allergy' && result[existingIndex]?.kind === 'preference') {
        const id = safeString(record.id) || `draft_${kind}_${existingIndex}`;
        result[existingIndex] = { id, kind, value };
      }
      continue;
    }
    indexByValue.set(dedupeKey, result.length);
    const id = safeString(record.id) || `draft_${kind}_${result.length}`;
    result.push({ id, kind, value });
  }

  return result;
}

/** Draft-safe constraint inputs (IDs optional). */
export function toConstraintInputs(constraints: DietaryConstraint[]): DietaryConstraintInput[] {
  return constraints.map(({ id, kind, value }) => ({ id, kind, value }));
}

/** Merges API profile record fields into normalized constraints + legacy list. */
export function resolveProfileConstraints(
  raw: ProfileApiRecord,
  responseLegacy?: string[],
): {
  dietary_constraints: DietaryConstraint[];
  legacy_constraints: string[];
  requires_constraint_review: boolean;
} {
  const dietary_constraints = normalizeDietaryConstraints(raw.dietary_constraints);
  const legacy_constraints =
    responseLegacy ??
    (raw.allergies && raw.allergies !== 'нет'
      ? raw.allergies.split(/[,;]+/).map((item) => item.trim()).filter(Boolean)
      : []);

  return {
    dietary_constraints,
    legacy_constraints,
    requires_constraint_review: legacy_constraints.length > 0,
  };
}

export function constraintsByKind(
  constraints: DietaryConstraint[],
  kind: DietaryConstraintKind,
): DietaryConstraint[] {
  return constraints.filter((item) => item.kind === kind);
}

export function removeConstraint(constraints: DietaryConstraint[], id: string): DietaryConstraint[] {
  return constraints.filter((item) => item.id !== id);
}

export function addConstraint(
  constraints: DietaryConstraint[],
  kind: DietaryConstraintKind,
  value: string,
): DietaryConstraint[] {
  const trimmed = value.trim();
  if (!trimmed) {
    return constraints;
  }
  return [
    ...constraints,
    { id: `draft_${kind}_${constraints.length}_${Date.now()}`, kind, value: trimmed },
  ];
}

export function classifyLegacyConstraint(
  constraints: DietaryConstraint[],
  legacyValue: string,
  kind: DietaryConstraintKind,
): { constraints: DietaryConstraint[]; legacy_constraints: string[] } {
  const trimmed = legacyValue.trim();
  if (!trimmed) {
    return { constraints, legacy_constraints: [] };
  }
  return {
    constraints: addConstraint(constraints, kind, trimmed),
    legacy_constraints: [],
  };
}
