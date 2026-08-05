"""Provenance / sources / evidence persistence helpers."""

from __future__ import annotations

import json
from typing import Any

import aiosqlite

from recipes.quality.config import SEED_PROVENANCE_NOTES
from recipes.quality.enums import CreationMethod, QualityStatus, SourceType
from recipes.quality.models import PatternEvidenceItem
from recipes.schemas import utc_now_iso


class ProvenanceStore:
    async def get_provenance(
        self, db: aiosqlite.Connection, recipe_id: str
    ) -> dict[str, Any] | None:
        cur = await db.execute(
            "SELECT * FROM recipe_provenance WHERE recipe_id = ?", (recipe_id,)
        )
        row = await cur.fetchone()
        if row is None:
            return None
        if isinstance(row, aiosqlite.Row):
            return dict(row)
        cols = [d[0] for d in cur.description]
        return dict(zip(cols, row))

    async def list_sources(
        self, db: aiosqlite.Connection, recipe_id: str
    ) -> list[dict[str, Any]]:
        cur = await db.execute(
            "SELECT * FROM recipe_sources WHERE recipe_id = ? ORDER BY id", (recipe_id,)
        )
        rows = await cur.fetchall()
        if not rows:
            return []
        if isinstance(rows[0], aiosqlite.Row):
            return [dict(r) for r in rows]
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, r)) for r in rows]

    async def count_sources(self, db: aiosqlite.Connection, recipe_id: str) -> int:
        cur = await db.execute(
            "SELECT COUNT(*) FROM recipe_sources WHERE recipe_id = ?", (recipe_id,)
        )
        return int((await cur.fetchone())[0])

    async def ensure_default_provenance(
        self,
        db: aiosqlite.Connection,
        recipe_id: str,
        *,
        creation_method: CreationMethod = CreationMethod.AGENT_GENERATED,
        quality_status: QualityStatus = QualityStatus.SCHEMA_VALIDATED,
        notes: str = SEED_PROVENANCE_NOTES,
        created_by: str = "catalog_importer",
    ) -> None:
        existing = await self.get_provenance(db, recipe_id)
        if existing is not None:
            # Keep source_count in sync
            count = await self.count_sources(db, recipe_id)
            if int(existing.get("source_count") or 0) != count:
                await db.execute(
                    """
                    UPDATE recipe_provenance
                    SET source_count = ?, updated_at = ?
                    WHERE recipe_id = ?
                    """,
                    (count, utc_now_iso(), recipe_id),
                )
            return
        now = utc_now_iso()
        count = await self.count_sources(db, recipe_id)
        await db.execute(
            """
            INSERT INTO recipe_provenance (
                recipe_id, creation_method, quality_status, source_count,
                confidence_score, created_by, reviewed_by, reviewed_at,
                approved_by, approved_at, notes, created_at, updated_at
            ) VALUES (?, ?, ?, ?, NULL, ?, NULL, NULL, NULL, NULL, ?, ?, ?)
            """,
            (
                recipe_id,
                creation_method.value,
                quality_status.value,
                count,
                created_by,
                notes,
                now,
                now,
            ),
        )

    async def update_quality_status(
        self,
        db: aiosqlite.Connection,
        recipe_id: str,
        quality_status: QualityStatus,
        *,
        confidence_score: float | None = None,
        notes: str | None = None,
    ) -> None:
        now = utc_now_iso()
        await self.ensure_default_provenance(db, recipe_id)
        fields = ["quality_status = ?", "updated_at = ?"]
        params: list[Any] = [quality_status.value, now]
        if confidence_score is not None:
            fields.append("confidence_score = ?")
            params.append(confidence_score)
        if notes is not None:
            fields.append("notes = ?")
            params.append(notes)
        params.append(recipe_id)
        await db.execute(
            f"UPDATE recipe_provenance SET {', '.join(fields)} WHERE recipe_id = ?",
            params,
        )

    def validate_source_payload(self, source: dict[str, Any]) -> list[str]:
        errors: list[str] = []
        ref = (source.get("source_reference") or "").strip()
        title = (source.get("source_title") or "").strip()
        if not ref:
            errors.append("empty source_reference")
        if not title:
            errors.append("empty source_title")
        # Reject obvious placeholders
        lowered = ref.lower()
        if lowered in {"n/a", "na", "none", "example.com", "http://example.com", "https://example.com"}:
            errors.append("placeholder source_reference")
        try:
            SourceType(source.get("source_type"))
        except Exception:  # noqa: BLE001
            errors.append("invalid source_type")
        return errors

    def validate_quality_transition(
        self,
        *,
        quality_status: QualityStatus,
        source_count: int,
        has_human_or_expert_review: bool,
        has_kitchen_test_passed: bool,
        notes: str | None,
        approved_by: str | None,
        approved_at: str | None,
        creation_method: CreationMethod | None = None,
    ) -> list[str]:
        errors: list[str] = []
        if quality_status == QualityStatus.SOURCE_VERIFIED and source_count < 1:
            errors.append("source_verified requires at least one source")
        if quality_status == QualityStatus.SOURCE_VERIFIED and source_count == 1:
            # Soft policy preference from SOURCE_POLICY: prefer ≥2 independent sources.
            # Still allow a single authoritative source for simple technological facts.
            pass
        if (
            creation_method == CreationMethod.AGENT_GENERATED
            and quality_status == QualityStatus.SOURCE_VERIFIED
            and source_count < 1
        ):
            errors.append("agent_generated cannot be source_verified without sources")
        if quality_status == QualityStatus.KITCHEN_TESTED and not has_kitchen_test_passed:
            errors.append("kitchen_tested requires passed kitchen_test review")
        if quality_status == QualityStatus.APPROVED:
            if not (has_human_or_expert_review or has_kitchen_test_passed):
                errors.append("approved requires human_reviewed or kitchen_tested")
            if not approved_by or not approved_at:
                errors.append("approved requires approved_by and approved_at")
        if quality_status == QualityStatus.REJECTED and not (notes or "").strip():
            errors.append("rejected requires notes")
        return errors

    async def replace_derived_pattern_evidence(
        self,
        db: aiosqlite.Connection,
        recipe_id: str,
        evidence: list[PatternEvidenceItem],
        audit_version: str,
    ) -> None:
        """Replace non-manual derived evidence for this recipe/audit version."""
        await db.execute(
            """
            DELETE FROM recipe_pattern_evidence
            WHERE recipe_id = ? AND manually_overridden = 0
              AND (audit_version = ? OR audit_version IS NULL)
            """,
            (recipe_id, audit_version),
        )
        now = utc_now_iso()
        for item in evidence:
            await db.execute(
                """
                INSERT INTO recipe_pattern_evidence (
                    recipe_id, pattern_type, evidence_type, value_bool, score,
                    rule_code, evidence_json, computed_at, audit_version,
                    manually_overridden, override_reason
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, NULL)
                """,
                (
                    recipe_id,
                    item.pattern_type.value,
                    item.evidence_type.value,
                    None if item.value_bool is None else int(item.value_bool),
                    item.score,
                    item.rule_code,
                    json.dumps(item.evidence_json, ensure_ascii=False),
                    now,
                    audit_version,
                ),
            )
