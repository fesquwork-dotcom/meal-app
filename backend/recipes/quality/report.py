"""Markdown / summary formatting for quality audit reports."""

from __future__ import annotations

from collections import Counter
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from recipes.quality.audit import QualityAuditReport


def format_quality_summary(report: "QualityAuditReport") -> dict[str, Any]:
    warning_codes: Counter[str] = Counter()
    error_codes: Counter[str] = Counter()
    for r in report.results:
        for e in r.blocking_errors:
            error_codes[e.code] += 1
        for w in r.warnings:
            warning_codes[w.code] += 1
    return {
        "top_warnings": warning_codes.most_common(15),
        "blocking_codes": error_codes.most_common(15),
        "recipes_with_blocking": [
            r.recipe_id for r in report.results if r.blocking_errors
        ],
        "human_review_recommended": [
            r.recipe_id for r in report.results  # all agent seeds
        ],
        "kitchen_test_recommended": [
            r.recipe_id
            for r in report.results
            if any(
                rec.reason_code == "KITCHEN_TEST_RECOMMENDED"
                for rec in r.recommendations
            )
        ],
    }


def format_quality_markdown(report: "QualityAuditReport") -> str:
    summary = format_quality_summary(report)
    lines: list[str] = []
    lines.append("# Recipe Quality Report (Sprint 10.7 / 10.8)")
    lines.append("")
    lines.append("## 1. Executive Summary")
    lines.append("")
    lines.append(
        f"- Audited **{report.recipe_count}** recipes "
        f"(audit `{report.audit_version}`, mode `{report.mode}`)."
    )
    agent_n = report.creation_methods.get("agent_generated", 0)
    adapted_n = report.creation_methods.get("source_adapted", 0)
    lines.append(
        f"- Creation mix: **agent_generated**={agent_n}, **source_adapted**={adapted_n}."
    )
    with_sources = sum(
        1 for r in report.results if int(r.source_summary.get("source_count") or 0) > 0
    )
    lines.append(
        f"- Recipes with recorded sources: **{with_sources}** "
        f"(source_verified status count: **{report.source_verified_count}**)."
    )
    lines.append(
        "- Computational checks do **not** prove taste, kitchen timing, or storage safety."
    )
    lines.append(
        "- Nutrition snapshots were **not** recalculated from ingredients "
        "(ingredient nutrition database is empty)."
    )
    lines.append("- Kitchen testing is **absent**.")
    lines.append(
        f"- **Approved** recipes: **{report.approved_count}** "
        "(automatic approval is forbidden)."
    )
    lines.append(
        f"- Passed: {report.passed_count}, "
        f"with warnings: {report.warning_count}, "
        f"failed: {report.failed_count}."
    )
    if report.average_confidence is not None:
        lines.append(f"- Average confidence: **{report.average_confidence}**.")
    lines.append("")

    lines.append("## 2. Quality Status Distribution")
    lines.append("")
    if report.status_distribution:
        for status, count in sorted(report.status_distribution.items()):
            lines.append(f"- `{status}`: {count}")
    else:
        lines.append("- (no provenance yet)")
    lines.append("")

    lines.append("## 3. Creation Methods")
    lines.append("")
    for method, count in sorted(report.creation_methods.items()):
        lines.append(f"- `{method}`: {count}")
    lines.append("")

    lines.append("## 4. Source Verification")
    lines.append("")
    lines.append(f"- source_verified recipes: **{report.source_verified_count}**")
    lines.append("- Recipes without sources: all current seed recipes.")
    lines.append("- `source_verified = false` for the entire seed catalog.")
    lines.append("")

    lines.append("## 5. Computational Checks")
    lines.append("")
    lines.append(
        "Checks run: nutrition snapshot, yield, time, proportions, pattern derivation."
    )
    lines.append(
        f"- Suggested computationally_checked candidates without blocking errors: "
        f"{sum(1 for r in report.results if not r.blocking_errors)}"
    )
    lines.append("")

    def _section(title: str, prefix: str) -> None:
        lines.append(f"## {title}")
        lines.append("")
        found = False
        for r in report.results:
            items = [
                i
                for i in r.blocking_errors + r.warnings
                if i.code.startswith(prefix) or prefix in i.code
            ]
            if not items:
                continue
            found = True
            lines.append(f"### {r.recipe_id}")
            for i in items:
                lines.append(f"- `{i.code}` ({i.severity}): {i.message}")
            lines.append("")
        if not found:
            lines.append("- None.")
            lines.append("")

    _section("6. Nutrition Warnings", "NUTRITION_")
    _section("7. Yield Warnings", "YIELD_")
    # also base portion
    lines.append("## 7b. Portion Range Warnings")
    lines.append("")
    portion_found = False
    for r in report.results:
        items = [
            i
            for i in r.warnings
            if i.code == "BASE_PORTION_OUTSIDE_RECOMMENDED_RANGE"
        ]
        if items:
            portion_found = True
            lines.append(f"- `{r.recipe_id}`: {items[0].message}")
    if not portion_found:
        lines.append("- None.")
    lines.append("")

    _section("8. Time Warnings", "TIME_")
    # also cooking method codes
    lines.append("## 8b. Cooking / Step Time Codes")
    lines.append("")
    time_codes = {
        "STEP_DURATION_EXCEEDS_TOTAL",
        "COOKING_METHOD_TIME_SUSPICIOUS",
        "ACTIVE_TIME_INCONSISTENT",
        "COOKING_STEP_MISSING",
        "TEMPERATURE_MISSING_FOR_BAKING",
    }
    found_t = False
    for r in report.results:
        items = [i for i in r.blocking_errors + r.warnings if i.code in time_codes]
        if items:
            found_t = True
            for i in items:
                lines.append(f"- `{r.recipe_id}` `{i.code}`: {i.message}")
    if not found_t:
        lines.append("- None beyond informational notes.")
    lines.append("")

    _section("9. Proportion Warnings", "SEASONING_")
    lines.append("## 9b. Other Proportion Codes")
    lines.append("")
    prop_codes = {
        "OIL_RATIO_SUSPICIOUS",
        "DRY_GRAIN_LIQUID_NOT_FOUND",
        "MAIN_INGREDIENT_SHARE_SUSPICIOUS",
        "DUPLICATE_RECIPE_INGREDIENT",
    }
    found_p = False
    for r in report.results:
        items = [i for i in r.warnings if i.code in prop_codes]
        if items:
            found_p = True
            for i in items:
                lines.append(f"- `{r.recipe_id}` `{i.code}`: {i.message}")
    if not found_p:
        lines.append("- None.")
    lines.append("")

    lines.append("## 10. Pattern Evidence Summary")
    lines.append("")
    pattern_true: Counter[str] = Counter()
    for r in report.results:
        for e in r.pattern_evidence:
            if e.value_bool is True:
                pattern_true[e.pattern_type.value] += 1
    for pname, count in sorted(pattern_true.items()):
        lines.append(f"- `{pname}` true: {count}")
    lines.append("")
    lines.append(
        "- `budget_friendly` evidence is **declared** only (`BUDGET_NOT_PRICE_VERIFIED`)."
    )
    lines.append(
        "- `high_fiber` is **insufficient_data** without fiber nutrition fields."
    )
    lines.append("")

    lines.append("## 11. Unsupported Tags and Roles")
    lines.append("")
    for r in report.results:
        unsupported = [
            rec
            for rec in r.recommendations
            if rec.recommendation_type.value
            in {"remove_unsupported_tag", "review_role"}
        ]
        for rec in unsupported:
            lines.append(
                f"- `{r.recipe_id}` {rec.field}: {rec.reason_code} "
                f"(current={rec.current_value}, derived={rec.derived_value})"
            )
    lines.append("")

    lines.append("## 12. Goal Score Review")
    lines.append("")
    goal_found = False
    for r in report.results:
        for rec in r.recommendations:
            if rec.recommendation_type.value == "review_goal_score":
                goal_found = True
                lines.append(
                    f"- `{r.recipe_id}` {rec.field}: score={rec.current_value}, "
                    f"structural={rec.derived_value} ({rec.reason_code})"
                )
    if not goal_found:
        lines.append("- No large goal-score gaps flagged beyond informational incompleteness.")
    lines.append("")

    lines.append("## 13. Approval Blockers")
    lines.append("")
    lines.append("No recipe is auto-approved. Typical blockers remain:")
    lines.append("- human_reviewed / kitchen_tested required")
    lines.append("- human approval record required")
    lines.append("- recipes without sources still blocked on source verification")
    lines.append("- source_verified is the maximum automatic gate status")
    lines.append("")
    if summary["recipes_with_blocking"]:
        lines.append("Recipes with computational blocking errors:")
        for rid in summary["recipes_with_blocking"]:
            lines.append(f"- `{rid}`")
    else:
        lines.append("No computational blocking errors in this run.")
    lines.append("")

    lines.append("## 14. Recipes Requiring Human Review")
    lines.append("")
    lines.append("All audited seed recipes require human culinary review.")
    for rid in summary["human_review_recommended"]:
        lines.append(f"- `{rid}`")
    lines.append("")

    lines.append("## 15. Recipes Recommended for Kitchen Testing")
    lines.append("")
    if summary["kitchen_test_recommended"]:
        for rid in summary["kitchen_test_recommended"]:
            lines.append(f"- `{rid}`")
    else:
        lines.append("- None specially flagged.")
    lines.append("")

    lines.append("## 16. Known Limitations")
    lines.append("")
    lines.append("- Agent-generated YAML is schema-valid, not kitchen-proven.")
    lines.append("- No invented source URLs or cookbook citations.")
    lines.append("- Ingredient nutrition table exists but is empty in this sprint.")
    lines.append("- Pattern evidence is structural/declared, not culinary proof.")
    lines.append("- Automatic audit may assign up to `source_verified` when ≥2 sources and checks pass; never approved / human_reviewed / kitchen_tested.")
    lines.append("- Selector weights, hard filters, MenuPlan, Claude pipeline, and Basket Engine are unchanged.")
    lines.append("")
    lines.append(f"_Generated at {report.completed_at or report.started_at}_")
    lines.append("")
    return "\n".join(lines)
