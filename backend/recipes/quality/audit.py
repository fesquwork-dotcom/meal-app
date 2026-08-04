"""Quality audit runs over the catalog."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

import aiosqlite

import database
from recipes.quality.config import AUDIT_VERSION
from recipes.quality.enums import ReviewOutcome
from recipes.quality.gate import RecipeQualityGate
from recipes.quality.models import RecipeQualityResult
from recipes.quality.provenance import ProvenanceStore
from recipes.quality.report import format_quality_markdown, format_quality_summary
from recipes.repository import RecipeRepository
from recipes.schemas import utc_now_iso

AuditMode = Literal["read_only", "apply"]


@dataclass
class QualityAuditReport:
    audit_version: str
    mode: AuditMode
    started_at: str
    completed_at: str | None = None
    recipe_count: int = 0
    passed_count: int = 0
    warning_count: int = 0
    failed_count: int = 0
    audit_run_id: int | None = None
    results: list[RecipeQualityResult] = field(default_factory=list)
    status_distribution: dict[str, int] = field(default_factory=dict)
    creation_methods: dict[str, int] = field(default_factory=dict)
    source_verified_count: int = 0
    human_reviewed_count: int = 0
    kitchen_tested_count: int = 0
    approved_count: int = 0
    average_confidence: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "audit_version": self.audit_version,
            "mode": self.mode,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "recipe_count": self.recipe_count,
            "passed_count": self.passed_count,
            "warning_count": self.warning_count,
            "failed_count": self.failed_count,
            "audit_run_id": self.audit_run_id,
            "status_distribution": self.status_distribution,
            "creation_methods": self.creation_methods,
            "source_verified_count": self.source_verified_count,
            "human_reviewed_count": self.human_reviewed_count,
            "kitchen_tested_count": self.kitchen_tested_count,
            "approved_count": self.approved_count,
            "average_confidence": self.average_confidence,
            "results": [r.to_dict() for r in self.results],
            "summary": format_quality_summary(self),
        }


class RecipeQualityAuditor:
    def __init__(self, db_path: Path | str | None = None) -> None:
        self.db_path = Path(db_path) if db_path else database.resolve_database_path()
        self.gate = RecipeQualityGate()
        self.store = ProvenanceStore()
        self.repo = RecipeRepository(self.db_path)

    async def run(
        self,
        *,
        mode: AuditMode = "read_only",
        recipe_id: str | None = None,
        ensure_provenance: bool = True,
    ) -> QualityAuditReport:
        started = utc_now_iso()
        report = QualityAuditReport(
            audit_version=AUDIT_VERSION,
            mode=mode,
            started_at=started,
        )

        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            from recipes.db import ensure_recipe_catalog_tables

            await ensure_recipe_catalog_tables(db)

            if recipe_id:
                ids = [recipe_id]
            else:
                cur = await db.execute("SELECT id FROM recipes ORDER BY id")
                ids = [r["id"] for r in await cur.fetchall()]

            cur = await db.execute(
                """
                INSERT INTO recipe_quality_audit_runs (
                    audit_version, started_at, completed_at, recipe_count,
                    passed_count, warning_count, failed_count,
                    configuration_json, mode
                ) VALUES (?, ?, NULL, 0, 0, 0, 0, ?, ?)
                """,
                (
                    AUDIT_VERSION,
                    started,
                    json.dumps({"recipe_id_filter": recipe_id}, ensure_ascii=False),
                    mode,
                ),
            )
            run_id = cur.lastrowid
            report.audit_run_id = run_id

            for rid in ids:
                if ensure_provenance:
                    await self.store.ensure_default_provenance(db, rid)

                recipe = await self.repo.get_recipe_with_dependencies(rid)
                if recipe is None:
                    continue

                result = await self.gate.evaluate(recipe, db, mode=mode)
                report.results.append(result)

                outcome = ReviewOutcome.PASSED
                if result.blocking_errors:
                    outcome = ReviewOutcome.FAILED
                    report.failed_count += 1
                elif result.warnings:
                    outcome = ReviewOutcome.PASSED_WITH_WARNINGS
                    report.warning_count += 1
                else:
                    report.passed_count += 1

                await db.execute(
                    """
                    INSERT INTO recipe_quality_audit_results (
                        audit_run_id, recipe_id, outcome,
                        error_codes_json, warning_codes_json, metrics_json, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        run_id,
                        rid,
                        outcome.value,
                        json.dumps(
                            [e.code for e in result.blocking_errors], ensure_ascii=False
                        ),
                        json.dumps(
                            [w.code for w in result.warnings], ensure_ascii=False
                        ),
                        json.dumps(
                            {
                                "suggested": result.suggested_quality_status.value,
                                "confidence": result.confidence_score,
                            },
                            ensure_ascii=False,
                        ),
                        utc_now_iso(),
                    ),
                )

                # Link a system review row to this audit run (one metadata review per run)
                await db.execute(
                    """
                    INSERT INTO recipe_quality_reviews (
                        recipe_id, review_type, outcome, reviewer_type,
                        reviewer_identifier, summary, details_json, audit_run_id, created_at
                    ) VALUES (?, 'metadata', ?, 'system', ?, ?, ?, ?, ?)
                    """,
                    (
                        rid,
                        outcome.value,
                        f"quality_audit:{AUDIT_VERSION}",
                        f"Audit {AUDIT_VERSION} ({mode})",
                        json.dumps(
                            {
                                "blocking": [e.code for e in result.blocking_errors],
                                "warnings": [w.code for w in result.warnings][:20],
                            },
                            ensure_ascii=False,
                        ),
                        run_id,
                        utc_now_iso(),
                    ),
                )

            # Status distribution after apply/read
            cur = await db.execute(
                """
                SELECT quality_status, COUNT(*) AS c
                FROM recipe_provenance GROUP BY quality_status
                """
            )
            report.status_distribution = {
                r["quality_status"]: r["c"] for r in await cur.fetchall()
            }
            cur = await db.execute(
                """
                SELECT creation_method, COUNT(*) AS c
                FROM recipe_provenance GROUP BY creation_method
                """
            )
            report.creation_methods = {
                r["creation_method"]: r["c"] for r in await cur.fetchall()
            }

            for key, attr in (
                ("source_verified", "source_verified_count"),
                ("human_reviewed", "human_reviewed_count"),
                ("kitchen_tested", "kitchen_tested_count"),
                ("approved", "approved_count"),
            ):
                setattr(report, attr, report.status_distribution.get(key, 0))

            confidences = [
                r.confidence_score
                for r in report.results
                if r.confidence_score is not None
            ]
            if confidences:
                report.average_confidence = round(
                    sum(confidences) / len(confidences), 3
                )

            completed = utc_now_iso()
            report.completed_at = completed
            report.recipe_count = len(report.results)
            await db.execute(
                """
                UPDATE recipe_quality_audit_runs
                SET completed_at = ?, recipe_count = ?, passed_count = ?,
                    warning_count = ?, failed_count = ?
                WHERE id = ?
                """,
                (
                    completed,
                    report.recipe_count,
                    report.passed_count,
                    report.warning_count,
                    report.failed_count,
                    run_id,
                ),
            )
            await db.commit()

        return report

    def write_markdown(self, report: QualityAuditReport, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(format_quality_markdown(report), encoding="utf-8")
