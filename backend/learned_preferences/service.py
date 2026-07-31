"""Read/write orchestration for Learned Preferences.

Candidates are derived only from existing *accepted* Learning recommendations
(no new rules, no automatic creation). A durable row is written solely on an
explicit user accept/revoke. Nothing here influences Decision or planning.
"""

from __future__ import annotations

import json
import logging
from typing import get_args

import config
from learned_preferences.api_models import (
    LearnedPreferenceEffectivenessPayload,
    LearnedPreferencesResponse,
    to_preferences_response,
)
from learned_preferences.effectiveness_models import (
    LearnedPreferenceEffectivenessResponse,
)
from learned_preferences.effectiveness_service import (
    LearnedPreferenceEffectivenessService,
)
from learned_preferences.exceptions import (
    LearnedPreferenceNotAvailableError,
    LearnedPreferenceNotFoundError,
)
from learned_preferences.models import (
    LEARNED_PREFERENCE_VERSION,
    LearnedPreference,
    LearnedPreferenceCollection,
    LearnedPreferenceConfidence,
    LearnedPreferenceEvidence,
    LearnedPreferenceType,
)
from learned_preferences.presentation import (
    LEARNED_PREFERENCE_BASIS,
    LEARNED_PREFERENCE_SUMMARIES,
    LEARNED_PREFERENCE_TITLES,
)
from learned_preferences.records import LearnedPreferenceRecord
from learned_preferences.repository import (
    LearnedPreferenceRepository,
    preference_key,
)
from learning.repository import LearningRepository

logger = logging.getLogger(__name__)

_SOURCE = "decision_learning"

_VALID_TYPES = frozenset(get_args(LearnedPreferenceType))
_VALID_CONFIDENCE = frozenset(get_args(LearnedPreferenceConfidence))

# Existing accepted recommendation types -> learned preference types.
# Only enable-style recommendations map; the rest have no learned meaning in v1.
_RECOMMENDATION_TO_TYPE: dict[str, LearnedPreferenceType] = {
    "profile_enable_prefer_familiar_meals": "prefer_familiar_meals",
    "profile_enable_prefer_faster_meals": "prefer_fast_meals",
}

# Deterministic display order by lifecycle relevance.
_STATUS_ORDER = {
    "active": 0,
    "accepted": 1,
    "candidate": 2,
    "revoked": 3,
    "archived": 4,
}

_EVALUABLE_TYPES = frozenset({"prefer_familiar_meals", "prefer_fast_meals"})


def _to_effectiveness_payload(
    response: LearnedPreferenceEffectivenessResponse | None,
) -> LearnedPreferenceEffectivenessPayload | None:
    if response is None:
        return None
    return LearnedPreferenceEffectivenessPayload(
        status=response.status,
        confidence=response.confidence,
        evidence_plans=response.evidence_plans,
        generation=response.generation,
        title=response.title,
        summary=response.summary,
        evidence_text=response.evidence_text,
        limitations=list(response.limitations),
    )


class LearnedPreferenceService:
    def __init__(
        self,
        *,
        repository: LearnedPreferenceRepository | None = None,
        learning_repository: LearningRepository | None = None,
        effectiveness_service: LearnedPreferenceEffectivenessService
        | None = None,
    ) -> None:
        self._repository = repository or LearnedPreferenceRepository()
        self._learning_repository = learning_repository or LearningRepository()
        self._effectiveness = (
            effectiveness_service or LearnedPreferenceEffectivenessService()
        )

    async def list_preferences(self, user_id: int) -> LearnedPreferencesResponse:
        records = await self._repository.list_for_user(user_id)
        persisted: dict[str, LearnedPreference] = {}
        for record in records:
            preference = self._record_to_preference(record)
            if preference is not None:
                persisted[preference.id] = preference

        candidates = await self._derive_candidates(user_id)
        merged = dict(persisted)
        for candidate in candidates:
            # A persisted decision always wins over a freshly derived candidate.
            merged.setdefault(candidate.id, candidate)

        preferences = sorted(
            merged.values(),
            key=lambda item: (_STATUS_ORDER.get(item.status, 9), item.id),
        )[:10]
        effectiveness_by_type = await self._effectiveness_map(
            user_id, preferences
        )
        logger.info(
            "learned_preferences_listed count=%s adaptive_enabled=%s",
            len(preferences),
            config.ADAPTIVE_PREFERENCES,
        )
        return to_preferences_response(
            LearnedPreferenceCollection(preferences=preferences),
            effectiveness_by_type=effectiveness_by_type,
        )

    async def _effectiveness_map(
        self, user_id: int, preferences: list[LearnedPreference]
    ) -> dict[str, LearnedPreferenceEffectivenessPayload | None]:
        types = sorted(
            {
                preference.type
                for preference in preferences
                if preference.status in {"active", "revoked"}
                and preference.type in _EVALUABLE_TYPES
            }
        )
        if not types:
            return {}
        try:
            raw = await self._effectiveness.get_all_effectiveness(
                user_id, types  # type: ignore[arg-type]
            )
        except Exception as exc:
            logger.warning(
                "learned_preference_effectiveness_unavailable error_type=%s",
                type(exc).__name__,
            )
            return {preference_type: None for preference_type in types}
        return {
            preference_type: _to_effectiveness_payload(payload)
            for preference_type, payload in raw.items()
        }

    async def load_active_for_decision(
        self, user_id: int
    ) -> list[LearnedPreference]:
        """Server-owned Decision input. No candidates or revoked rows."""
        records = await self._repository.list_for_user(user_id)
        active = [
            preference
            for record in records
            if record.status == "active"
            and (preference := self._record_to_preference(record)) is not None
        ]
        active.sort(key=lambda item: (item.type, item.version))
        return active

    async def accept(
        self, user_id: int, preference_id: str
    ) -> LearnedPreferencesResponse:
        existing = await self._repository.get(user_id, preference_id)
        if existing is not None:
            if existing.status == "active":
                return await self._single_response(user_id, existing)
            record = await self._repository.transition(
                user_id=user_id,
                preference_id=preference_id,
                target_status="active",
                allowed_from=("candidate", "accepted"),
            )
        else:
            candidate = await self._require_candidate(user_id, preference_id)
            record = await self._repository.create(
                user_id=user_id,
                preference_id=candidate.id,
                preference_type=candidate.type,
                source=_SOURCE,
                evidence_json=self._evidence_json(candidate),
                preference_json=self._preference_json(candidate),
                status="active",
            )
        logger.info("learned_preference_accepted type=%s", record.type)
        return await self._single_response(user_id, record)

    async def revoke(
        self, user_id: int, preference_id: str
    ) -> LearnedPreferencesResponse:
        existing = await self._repository.get(user_id, preference_id)
        if existing is not None:
            if existing.status == "revoked":
                return await self._single_response(user_id, existing)
            record = await self._repository.transition(
                user_id=user_id,
                preference_id=preference_id,
                target_status="revoked",
                allowed_from=("candidate", "accepted", "active"),
            )
        else:
            candidate = await self._require_candidate(user_id, preference_id)
            # Persist the declined candidate so it does not resurface.
            record = await self._repository.create(
                user_id=user_id,
                preference_id=candidate.id,
                preference_type=candidate.type,
                source=_SOURCE,
                evidence_json=self._evidence_json(candidate),
                preference_json=self._preference_json(candidate),
                status="revoked",
            )
        logger.info("learned_preference_revoked type=%s", record.type)
        return await self._single_response(user_id, record)

    async def dismiss_review(
        self, user_id: int, preference_id: str
    ) -> LearnedPreferencesResponse:
        """Persist 'keep active' review dismiss for the current evidence cohort.

        Does not change preference status, Profile, Decision, Preview, or MenuPlan.
        """
        existing = await self._repository.get(user_id, preference_id)
        if existing is None:
            raise LearnedPreferenceNotFoundError(preference_id)
        if existing.status != "active":
            raise LearnedPreferenceNotAvailableError(existing.status)

        preference = self._record_to_preference(existing)
        if preference is None:
            raise LearnedPreferenceNotFoundError(preference_id)

        generation = 0
        if preference.type in _EVALUABLE_TYPES:
            effectiveness = await self._effectiveness.get_effectiveness(
                user_id, preference.type
            )
            if effectiveness is not None:
                generation = effectiveness.generation

        record = await self._repository.set_last_review_generation(
            user_id=user_id,
            preference_id=preference_id,
            generation=generation,
        )
        logger.info(
            "learned_preference_review_dismissed type=%s generation=%s",
            record.type,
            generation,
        )
        return await self._single_response(user_id, record)

    async def _require_candidate(
        self, user_id: int, preference_id: str
    ) -> LearnedPreference:
        for candidate in await self._derive_candidates(user_id):
            if candidate.id == preference_id:
                return candidate
        raise LearnedPreferenceNotFoundError(preference_id)

    async def _derive_candidates(self, user_id: int) -> list[LearnedPreference]:
        recommendations = await self._learning_repository.list_visible(user_id)
        candidates: dict[str, LearnedPreference] = {}
        for recommendation in recommendations:
            # Only recommendations the user already accepted seed a candidate.
            if recommendation.status != "accepted":
                continue
            lp_type = _RECOMMENDATION_TO_TYPE.get(
                recommendation.recommendation_type
            )
            if lp_type is None:
                continue
            confidence = (
                recommendation.confidence
                if recommendation.confidence in _VALID_CONFIDENCE
                else "moderate"
            )
            candidate = self._build_preference(
                lp_type=lp_type,
                status="candidate",
                confidence=confidence,
            )
            candidates.setdefault(candidate.id, candidate)
        return list(candidates.values())

    def _record_to_preference(
        self, record: LearnedPreferenceRecord
    ) -> LearnedPreference | None:
        if record.type not in _VALID_TYPES:
            logger.warning("learned_preference_unavailable reason=unknown_type")
            return None
        confidence = self._parse_confidence(record.evidence_json)
        return self._build_preference(
            lp_type=record.type,  # type: ignore[arg-type]
            status=record.status,  # type: ignore[arg-type]
            confidence=confidence,
            id_override=record.id,
            created_at=record.created_at,
            accepted_at=record.accepted_at,
            revoked_at=record.revoked_at,
            archived_at=record.archived_at,
            last_review_generation=record.last_review_generation,
        )

    def _build_preference(
        self,
        *,
        lp_type: LearnedPreferenceType,
        status: str,
        confidence: LearnedPreferenceConfidence,
        id_override: str | None = None,
        created_at: str | None = None,
        accepted_at: str | None = None,
        revoked_at: str | None = None,
        archived_at: str | None = None,
        last_review_generation: int | None = None,
    ) -> LearnedPreference:
        return LearnedPreference(
            id=id_override or preference_key(lp_type),
            type=lp_type,
            status=status,  # type: ignore[arg-type]
            source=_SOURCE,
            confidence=confidence,
            title=LEARNED_PREFERENCE_TITLES[lp_type],
            summary=LEARNED_PREFERENCE_SUMMARIES[lp_type],
            evidence=LearnedPreferenceEvidence(
                source=_SOURCE,
                confidence=confidence,
                basis=LEARNED_PREFERENCE_BASIS[lp_type],
            ),
            version=LEARNED_PREFERENCE_VERSION,
            created_at=created_at,
            accepted_at=accepted_at,
            revoked_at=revoked_at,
            archived_at=archived_at,
            last_review_generation=last_review_generation,
        )

    async def _single_response(
        self,
        user_id: int,
        record_or_preference: LearnedPreferenceRecord | LearnedPreference,
    ) -> LearnedPreferencesResponse:
        preference = (
            record_or_preference
            if isinstance(record_or_preference, LearnedPreference)
            else self._record_to_preference(record_or_preference)
        )
        preferences = [preference] if preference is not None else []
        effectiveness_by_type = await self._effectiveness_map(
            user_id, preferences
        )
        return to_preferences_response(
            LearnedPreferenceCollection(preferences=preferences),
            effectiveness_by_type=effectiveness_by_type,
        )

    @staticmethod
    def _parse_confidence(evidence_json: str) -> LearnedPreferenceConfidence:
        try:
            data = json.loads(evidence_json)
        except (ValueError, TypeError):
            return "moderate"
        value = data.get("confidence") if isinstance(data, dict) else None
        return value if value in _VALID_CONFIDENCE else "moderate"

    @staticmethod
    def _evidence_json(preference: LearnedPreference) -> str:
        return json.dumps(
            {"source": _SOURCE, "confidence": preference.confidence},
            ensure_ascii=False,
        )

    @staticmethod
    def _preference_json(preference: LearnedPreference) -> str:
        return json.dumps({"type": preference.type}, ensure_ascii=False)
