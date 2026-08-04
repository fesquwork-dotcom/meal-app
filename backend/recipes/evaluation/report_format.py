"""Markdown and console rendering for coverage reports."""

from __future__ import annotations

from recipes.evaluation.models import CatalogCoverageReport, ScenarioCoverageStatus


def format_console_report(
    report: CatalogCoverageReport,
    *,
    show_critical: bool = False,
    show_recommendations: bool = False,
) -> str:
    lines = [
        "Recipe Catalog Coverage",
        "",
        f"Recipes: {report.catalog_recipe_count}",
        f"Scenarios: {report.total_scenarios}",
        "",
        f"Covered: {report.covered_scenarios}",
        f"Weak: {report.weak_scenarios}",
        f"Critical: {report.critical_scenarios}",
        f"Expected empty: {report.expected_empty_scenarios}",
        "",
        f"Weighted coverage: {report.weighted_coverage_score * 100:.1f}%",
        "",
        "Coverage:",
    ]
    for meal, score in report.coverage_by_meal_type.items():
        lines.append(f"- {meal.title()}: {score * 100:.0f}%")

    lines.append("")
    lines.append("Top gaps:")
    for idx, cluster in enumerate(report.catalog_gap_clusters[:10], start=1):
        lines.append(
            f"{idx}. [{cluster.severity.value}] {cluster.title} "
            f"(scenarios={len(cluster.affected_scenario_ids)}, "
            f"missing={cluster.missing_candidate_count})"
        )

    if show_critical:
        lines.append("")
        lines.append("Critical scenarios:")
        for r in report.scenario_results:
            if r.status == ScenarioCoverageStatus.CRITICAL:
                lines.append(
                    f"- {r.scenario_id}: actual={r.actual_candidates} "
                    f"expected={r.expected_min_candidates} "
                    f"filters={r.dominant_filter_reasons}"
                )

    if show_recommendations:
        lines.append("")
        lines.append("Recommendations:")
        for rec in report.recommended_additions[:15]:
            lines.append(
                f"- [{rec.recommendation_type.value}] {rec.suggested_name} "
                f"(impact≈{rec.estimated_scenario_impact})"
            )

    return "\n".join(lines) + "\n"


def format_markdown_report(report: CatalogCoverageReport) -> str:
    lines = [
        "# Recipe Catalog Coverage Report",
        "",
        f"Generated: `{report.generated_at}`",
        f"Catalog recipes: **{report.catalog_recipe_count}**",
        f"Schema version: `{report.catalog_schema_version}`",
        "",
        "## Executive Summary",
        "",
        f"- Scenarios: **{report.total_scenarios}**",
        f"- Covered: **{report.covered_scenarios}**",
        f"- Weak: **{report.weak_scenarios}**",
        f"- Critical: **{report.critical_scenarios}**",
        f"- Expected empty: **{report.expected_empty_scenarios}**",
        f"- Weighted coverage: **{report.weighted_coverage_score * 100:.1f}%**",
        "",
        "## Coverage by Meal Type",
        "",
        "| Meal type | Coverage |",
        "|-----------|----------|",
    ]
    for meal, score in report.coverage_by_meal_type.items():
        lines.append(f"| {meal} | {score * 100:.1f}% |")

    lines.extend(
        [
            "",
            "## Coverage by Goal",
            "",
            "| Goal | Coverage |",
            "|------|----------|",
        ]
    )
    for goal, score in report.coverage_by_goal.items():
        lines.append(f"| {goal} | {score * 100:.1f}% |")

    lines.extend(
        [
            "",
            "## Coverage by Scenario Group",
            "",
            "| Group | Coverage |",
            "|-------|----------|",
        ]
    )
    for group, score in report.coverage_by_scenario_group.items():
        lines.append(f"| {group} | {score * 100:.1f}% |")

    lines.extend(["", "## Weak Scenarios", ""])
    for r in report.scenario_results:
        if r.status == ScenarioCoverageStatus.WEAK:
            lines.append(
                f"- `{r.scenario_id}`: {r.actual_candidates}/{r.expected_min_candidates} "
                f"(ratio={r.coverage_ratio:.2f})"
            )

    lines.extend(["", "## Critical Scenarios", ""])
    critical = [
        r
        for r in report.scenario_results
        if r.status == ScenarioCoverageStatus.CRITICAL
    ]
    if not critical:
        lines.append("_None_")
    for r in critical:
        lines.append(
            f"- `{r.scenario_id}`: expected {r.expected_min_candidates}, "
            f"filters={', '.join(r.dominant_filter_reasons) or 'n/a'}"
        )

    lines.extend(
        [
            "",
            "## Common Filter Reasons",
            "",
            "| Reason | Recipes removed (sum) | Scenarios hit |",
            "|--------|----------------------|---------------|",
        ]
    )
    for code, total in report.common_filter_failures.items():
        hits = report.common_filter_scenario_hits.get(code, 0)
        lines.append(f"| `{code}` | {total} | {hits} |")

    lines.extend(["", "## Gap Clusters", ""])
    for cluster in report.catalog_gap_clusters[:20]:
        lines.append(
            f"### {cluster.id}: {cluster.title}",
        )
        lines.append("")
        lines.append(f"- Severity: `{cluster.severity.value}`")
        lines.append(f"- Scenarios: {', '.join(f'`{s}`' for s in cluster.affected_scenario_ids)}")
        lines.append(f"- Missing candidates (sum deficit): {cluster.missing_candidate_count}")
        lines.append(
            f"- Dominant filters: {', '.join(cluster.dominant_filter_reasons) or 'n/a'}"
        )
        lines.append("")

    lines.extend(["", "## Recommended Recipe Additions", ""])
    adds = [
        r
        for r in report.recommended_additions
        if r.recommendation_type.value == "add_recipe"
    ]
    if not adds:
        lines.append("_None_")
    for rec in adds:
        lines.append(
            f"1. **{rec.suggested_name}** — meal=`{rec.primary_meal_type}`, "
            f"goals={rec.target_goals}, time≤{rec.max_total_time_minutes}, "
            f"budget=`{rec.budget_class}`, protein=`{rec.protein_source}`, "
            f"impact≈{rec.estimated_scenario_impact}, gaps={rec.addresses_gap_ids}"
        )

    lines.extend(["", "## Metadata Review Recommendations", ""])
    meta = [
        r
        for r in report.recommended_additions
        if r.recommendation_type.value != "add_recipe"
    ]
    if not meta:
        lines.append("_None_")
    for rec in meta:
        lines.append(
            f"- [{rec.recommendation_type.value}] {rec.suggested_name} "
            f"(recipe=`{rec.related_recipe_id}`)"
        )

    lines.append("")
    return "\n".join(lines)
