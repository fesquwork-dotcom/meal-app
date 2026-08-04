"""Future-facing quality status filter (not wired into Selector hard filters)."""

from __future__ import annotations

from recipes.quality.enums import QUALITY_STATUS_RANK, QualityStatus


def meets_minimum_quality(
    current: QualityStatus | None,
    minimum: QualityStatus | None,
) -> bool:
    """Return True when no minimum is set, or current rank >= minimum rank.

    Rejected recipes never pass a positive minimum.
    """
    if minimum is None:
        return True
    if current is None:
        return False
    if current == QualityStatus.REJECTED:
        return False
    return QUALITY_STATUS_RANK.get(current, -1) >= QUALITY_STATUS_RANK.get(minimum, 0)
