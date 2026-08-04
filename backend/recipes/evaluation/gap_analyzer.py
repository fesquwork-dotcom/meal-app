"""Cluster weak/critical scenarios into catalog gaps."""

from __future__ import annotations

from collections import Counter, defaultdict

from recipes.evaluation.models import (
    CatalogGapCluster,
    EvaluationScenario,
    EvaluationScenarioResult,
    GapSeverity,
    ScenarioCoverageStatus,
    ScenarioGroup,
)


def _cluster_key(scenario: EvaluationScenario) -> tuple:
    ctx = scenario.context
    return (
        ctx.meal_type.value,
        ctx.goal.value if ctx.goal else None,
        ctx.max_total_time_minutes,
        tuple(sorted(b.value for b in (ctx.allowed_budget_classes or []))) or None,
        tuple(sorted(p.value for p in ctx.excluded_protein_sources)) or None,
        tuple(sorted(p.value for p in ctx.preferred_protein_sources)) or None,
        tuple(sorted(ctx.excluded_ingredient_ids)) or None,
        tuple(sorted(r.value for r in ctx.desired_roles)) or None,
        bool(ctx.prefer_batch_friendly),
        bool(ctx.allow_leftovers),
        bool(ctx.family_mode),
        tuple(sorted(e.value for e in ctx.available_equipment))
        if ctx.available_equipment is not None
        else None,
    )


def _missing_oven(ctx) -> bool:
    if ctx.available_equipment is None:
        return False
    vals = {e.value for e in ctx.available_equipment}
    return "oven" not in vals and len(vals) > 0


def _title_for(scenario: EvaluationScenario) -> str:
    ctx = scenario.context
    parts = [ctx.meal_type.value]
    if ctx.goal:
        parts.append(ctx.goal.value)
    if ctx.max_total_time_minutes:
        parts.append(f"≤{ctx.max_total_time_minutes}m")
    if ctx.excluded_protein_sources:
        parts.append(
            "no_" + "_".join(sorted(p.value for p in ctx.excluded_protein_sources)[:2])
        )
    if ctx.preferred_protein_sources:
        parts.append(
            "pref_"
            + "_".join(sorted(p.value for p in ctx.preferred_protein_sources)[:2])
        )
    if ctx.family_mode:
        parts.append("family")
    if ctx.prefer_batch_friendly:
        parts.append("batch")
    if _missing_oven(ctx):
        parts.append("no_oven")
    return " / ".join(parts)


def _severity(
    members: list[EvaluationScenarioResult],
    scenarios: dict[str, EvaluationScenario],
) -> GapSeverity:
    critical = [m for m in members if m.status == ScenarioCoverageStatus.CRITICAL]
    important = []
    for m in members:
        sc = scenarios.get(m.scenario_id)
        if sc is None:
            continue
        if sc.scenario_group in {
            ScenarioGroup.BASELINE,
            ScenarioGroup.GOAL,
            ScenarioGroup.COMBINED,
        } and sc.weight >= 1.0:
            important.append(m)

    if any(m.status == ScenarioCoverageStatus.CRITICAL for m in important):
        return GapSeverity.HIGH
    if critical and any(m.weight >= 1.0 for m in critical):
        return GapSeverity.HIGH
    if sum(1 for m in important if m.coverage_ratio < 0.5) >= 2:
        return GapSeverity.HIGH

    weak = [m for m in members if m.status == ScenarioCoverageStatus.WEAK]
    if len(weak) >= 2 or any(0.5 <= m.coverage_ratio < 0.8 for m in important):
        return GapSeverity.MEDIUM
    return GapSeverity.LOW


class CatalogGapAnalyzer:
    def analyze(
        self,
        results: list[EvaluationScenarioResult],
        scenarios_by_id: dict[str, EvaluationScenario],
    ) -> list[CatalogGapCluster]:
        weakish = [
            r
            for r in results
            if r.status
            in {ScenarioCoverageStatus.WEAK, ScenarioCoverageStatus.CRITICAL}
        ]
        buckets: dict[tuple, list[EvaluationScenarioResult]] = defaultdict(list)
        for result in weakish:
            scenario = scenarios_by_id.get(result.scenario_id)
            if scenario is None:
                continue
            # Stress gaps stay isolated with lower severity influence
            key = _cluster_key(scenario)
            buckets[key].append(result)

        def _sort_key(item: tuple) -> str:
            key, _members = item
            return repr(key)

        clusters: list[CatalogGapCluster] = []
        for idx, (key, members) in enumerate(sorted(buckets.items(), key=_sort_key)):
            members = sorted(members, key=lambda m: m.scenario_id)
            first = scenarios_by_id[members[0].scenario_id]
            ctx = first.context
            missing = sum(
                max(0, m.expected_min_candidates - m.actual_candidates) for m in members
            )
            reason_counter: Counter[str] = Counter()
            for m in members:
                for code in m.dominant_filter_reasons:
                    reason_counter[code] += 1

            cluster_id = f"gap_{idx:03d}_{ctx.meal_type.value}"
            clusters.append(
                CatalogGapCluster(
                    id=cluster_id,
                    title=_title_for(first),
                    affected_scenario_ids=[m.scenario_id for m in members],
                    meal_types=[ctx.meal_type.value],
                    goals=[ctx.goal.value] if ctx.goal else [],
                    time_limits=(
                        [ctx.max_total_time_minutes]
                        if ctx.max_total_time_minutes
                        else []
                    ),
                    budget_classes=(
                        [b.value for b in ctx.allowed_budget_classes]
                        if ctx.allowed_budget_classes
                        else []
                    ),
                    excluded_ingredients=sorted(ctx.excluded_ingredient_ids),
                    excluded_protein_sources=sorted(
                        p.value for p in ctx.excluded_protein_sources
                    ),
                    preferred_protein_sources=sorted(
                        p.value for p in ctx.preferred_protein_sources
                    ),
                    desired_roles=[r.value for r in ctx.desired_roles],
                    severity=_severity(members, scenarios_by_id),
                    missing_candidate_count=missing,
                    dominant_filter_reasons=[
                        c for c, _ in reason_counter.most_common(5)
                    ],
                )
            )

        severity_order = {
            GapSeverity.HIGH: 0,
            GapSeverity.MEDIUM: 1,
            GapSeverity.LOW: 2,
        }
        clusters.sort(
            key=lambda c: (
                severity_order[c.severity],
                -c.missing_candidate_count,
                -len(c.affected_scenario_ids),
                c.id,
            )
        )
        return clusters
