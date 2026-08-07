"""Map API reason_code / free-text reason onto catalog replacement semantics.

Existing wire vocabulary (memory.constants.ReplacementReasonCode) is preserved.
Sprint-facing local reasons are an internal scoring layer only.
"""

from __future__ import annotations

from enum import StrEnum

from memory.constants import ReplacementReasonCode
from strategy.replacement_models import ReplaceMealRequest


class CatalogReplacementReason(StrEnum):
    DONT_LIKE = "DONT_LIKE"
    TOO_LONG = "TOO_LONG"
    TOO_EXPENSIVE = "TOO_EXPENSIVE"
    INGREDIENT_UNAVAILABLE = "INGREDIENT_UNAVAILABLE"
    WANT_VARIETY = "WANT_VARIETY"
    GENERIC = "GENERIC"


_FASTER_HINTS = ("долго", "долг", "время", "быстр", "faster", "too long", "slow")
_EXPENSIVE_HINTS = ("дорог", "дорог", "бюджет", "expensive", "cost", "дешев")
_VARIETY_HINTS = ("разнообраз", "variety", "повтор", "надоел")
_DISLIKE_HINTS = ("не нрав", "dislike", "не хочу", "не любл")
_UNAVAIL_HINTS = ("нет ", "нет в", "unavailable", "закончил", "недоступ")


def resolve_catalog_reason(request: ReplaceMealRequest) -> CatalogReplacementReason:
    code = (request.reason_code or "").strip()
    if code == ReplacementReasonCode.FASTER.value:
        return CatalogReplacementReason.TOO_LONG
    if code == ReplacementReasonCode.DISLIKE_INGREDIENT.value:
        return CatalogReplacementReason.DONT_LIKE
    if code == ReplacementReasonCode.INGREDIENT_UNAVAILABLE.value:
        return CatalogReplacementReason.INGREDIENT_UNAVAILABLE

    text = (request.reason or "").strip().lower().replace("ё", "е")
    if text:
        if any(h in text for h in _UNAVAIL_HINTS) or request.target_ingredient:
            if request.target_ingredient or any(h in text for h in _UNAVAIL_HINTS):
                if any(h in text for h in _UNAVAIL_HINTS) or code == (
                    ReplacementReasonCode.INGREDIENT_UNAVAILABLE.value
                ):
                    return CatalogReplacementReason.INGREDIENT_UNAVAILABLE
        if any(h in text for h in _FASTER_HINTS):
            return CatalogReplacementReason.TOO_LONG
        if any(h in text for h in _EXPENSIVE_HINTS):
            return CatalogReplacementReason.TOO_EXPENSIVE
        if any(h in text for h in _VARIETY_HINTS):
            return CatalogReplacementReason.WANT_VARIETY
        if any(h in text for h in _DISLIKE_HINTS):
            return CatalogReplacementReason.DONT_LIKE
        if request.target_ingredient:
            return CatalogReplacementReason.DONT_LIKE

    if code in {
        ReplacementReasonCode.GENERIC.value,
        ReplacementReasonCode.OTHER.value,
        "",
    }:
        return CatalogReplacementReason.GENERIC
    return CatalogReplacementReason.GENERIC
