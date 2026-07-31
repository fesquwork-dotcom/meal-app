"""Applies user-selected conflict resolutions using server-owned state."""

from __future__ import annotations

import logging

import database
from api_models import ResolveConflictRequest
from dietary_constraints import DietaryConstraintKind, constraints_from_profile
from memory.exceptions import MemorySignalNotFoundError
from memory.service import MemoryService
from profile_validation import normalize_profile_for_persistence, validate_profile_payload
from strategy.conflict_id import is_valid_conflict_id
from strategy.conflict_targets import DetectedConflict
from strategy.conflicts import (
    find_detected_conflict,
    is_action_allowed,
    detect_strategy_conflicts,
)
from strategy.context import ProfileContext
from strategy.exceptions import ConflictNotFoundError, StrategyValidationError
from strategy.memory_context import StrategyMemoryContext
from strategy.preview_models import ConflictResolutionAction, ResolveConflictResponse
from strategy.behavior_context import StrategyBehaviorContext
from strategy.preview_token import PreviewTokenError, VerifiedPreviewToken, verify_preview_token
from strategy.versions import STRATEGY_PREVIEW_VERSION

logger = logging.getLogger(__name__)


class ConflictResolutionService:
    def __init__(self, memory_service: MemoryService | None = None) -> None:
        self._memory_service = memory_service or MemoryService()

    async def resolve(
        self,
        *,
        user_id: int,
        request: ResolveConflictRequest,
        profile: dict[str, object],
        profile_revision: int,
        memory_context: StrategyMemoryContext,
        memory_unavailable: bool,
        verified_token: VerifiedPreviewToken,
    ) -> ResolveConflictResponse:
        if not is_valid_conflict_id(request.conflict_id):
            raise StrategyValidationError(
                "Invalid conflict ID",
                code="CONFLICT_ID_INVALID",
            )

        action = request.action.value
        profile_context = ProfileContext.from_profile(profile)
        blocking, warnings = detect_strategy_conflicts(
            profile_context,
            memory_context,
            profile_revision=profile_revision,
            preview_version=STRATEGY_PREVIEW_VERSION,
        )
        detected = find_detected_conflict(blocking, warnings, request.conflict_id)
        if detected is None:
            logger.info(
                "conflict_not_found user_id=%s conflict_id=%s",
                user_id,
                request.conflict_id,
            )
            raise ConflictNotFoundError()

        if not is_action_allowed(detected.conflict.code, action):
            logger.info(
                "conflict_invalid_action user_id=%s conflict_code=%s action=%s",
                user_id,
                detected.conflict.code,
                action,
            )
            raise StrategyValidationError(
                "Action is not allowed for this conflict",
                code="CONFLICT_ACTION_NOT_ALLOWED",
            )

        logger.info(
            "conflict_resolution_attempted user_id=%s conflict_code=%s action=%s",
            user_id,
            detected.conflict.code,
            action,
        )

        if action == ConflictResolutionAction.DISMISS_MEMORY_SIGNAL.value:
            await self._dismiss_signal(user_id, detected)
            logger.info(
                "conflict_resolved user_id=%s conflict_code=%s action=%s",
                user_id,
                detected.conflict.code,
                action,
            )
            return ResolveConflictResponse(
                status="resolved",
                profile_revision=profile_revision,
                requires_new_preview=True,
            )

        if action == ConflictResolutionAction.REMOVE_PROFILE_PROTEIN.value:
            return await self._remove_protein(user_id, detected, profile, profile_revision)

        if action == ConflictResolutionAction.REMOVE_PROFILE_PREFERENCE.value:
            return await self._remove_preference(user_id, detected, profile, profile_revision)

        raise StrategyValidationError(
            "Unknown resolution action",
            code="CONFLICT_ACTION_INVALID",
        )

    async def _dismiss_signal(self, user_id: int, detected: DetectedConflict) -> None:
        signal_id = detected.target.memory_signal_id
        if not signal_id:
            raise StrategyValidationError(
                "Conflict has no memory signal",
                code="CONFLICT_SIGNAL_REQUIRED",
            )
        try:
            await self._memory_service.dismiss_signal(user_id, signal_id)
        except MemorySignalNotFoundError as exc:
            raise MemorySignalNotFoundError(str(exc)) from exc

    async def _remove_protein(
        self,
        user_id: int,
        detected: DetectedConflict,
        profile: dict[str, object],
        expected_revision: int,
    ) -> ResolveConflictResponse:
        protein = (detected.target.canonical_value or "").strip().lower()
        if not protein:
            logger.info("conflict_requires_input user_id=%s field=proteins", user_id)
            return ResolveConflictResponse(
                status="requires_input",
                code="PROFILE_REQUIRES_PROTEIN_SELECTION",
                field="proteins",
                message="Select a protein source to continue",
                requires_new_preview=True,
            )

        proteins = list(profile.get("proteins") or [])
        updated_proteins = [item for item in proteins if str(item).lower() != protein]
        if not updated_proteins:
            logger.info("conflict_requires_input user_id=%s field=proteins", user_id)
            return ResolveConflictResponse(
                status="requires_input",
                code="PROFILE_REQUIRES_PROTEIN_SELECTION",
                field="proteins",
                message="Select a protein source to continue",
                requires_new_preview=True,
            )

        return await self._save_profile_patch(
            user_id=user_id,
            profile=profile,
            expected_revision=expected_revision,
            patch={"proteins": updated_proteins},
            detected=detected,
            action=ConflictResolutionAction.REMOVE_PROFILE_PROTEIN.value,
        )

    async def _remove_preference(
        self,
        user_id: int,
        detected: DetectedConflict,
        profile: dict[str, object],
        expected_revision: int,
    ) -> ResolveConflictResponse:
        """Removes a preference-kind constraint. Safety constraints (allergy,
        intolerance) and legacy raw values are never removable here."""
        constraint_id = detected.target.constraint_id
        if not constraint_id:
            raise StrategyValidationError(
                "Conflict has no removable preference constraint",
                code="CONSTRAINT_NOT_REMOVABLE",
            )

        constraints = constraints_from_profile(profile)
        target = next((item for item in constraints if item.id == constraint_id), None)
        if target is None:
            raise StrategyValidationError(
                "Constraint not found",
                code="CONSTRAINT_NOT_REMOVABLE",
            )
        if target.kind != DietaryConstraintKind.PREFERENCE:
            logger.info(
                "constraint_removal_blocked user_id=%s kind=%s",
                user_id,
                target.kind.value,
            )
            raise StrategyValidationError(
                "Only preference constraints can be removed through conflict resolution",
                code="CONSTRAINT_NOT_REMOVABLE",
            )

        updated_constraints = [
            item.model_dump(mode="json") for item in constraints if item.id != constraint_id
        ]
        return await self._save_profile_patch(
            user_id=user_id,
            profile=profile,
            expected_revision=expected_revision,
            patch={"dietary_constraints": updated_constraints},
            detected=detected,
            action=ConflictResolutionAction.REMOVE_PROFILE_PREFERENCE.value,
        )

    async def _save_profile_patch(
        self,
        *,
        user_id: int,
        profile: dict[str, object],
        expected_revision: int,
        patch: dict[str, object],
        detected: DetectedConflict,
        action: str,
    ) -> ResolveConflictResponse:
        profile_payload = {
            "first_name": profile.get("first_name") or "",
            "budget": profile.get("budget"),
            "days": profile.get("days"),
            "meal_types": profile.get("meal_types"),
            "meals_per_day": profile.get("meals_per_day"),
            "persons": profile.get("persons"),
            "proteins": profile.get("proteins"),
            "goal": profile.get("goal"),
            "cooktime": profile.get("cooktime"),
            "allergies": profile.get("allergies"),
            "dietary_constraints": profile.get("dietary_constraints"),
            "store": profile.get("store"),
        }
        profile_payload.update(patch)

        validation = validate_profile_payload(profile_payload)
        if validation.status == "invalid":
            raise StrategyValidationError(
                validation.message or "Invalid profile",
                code=validation.code or "PROFILE_INVALID",
            )

        result = await database.save_profile_with_revision(
            user_id,
            normalize_profile_for_persistence(profile_payload),
            expected_revision,
        )
        if result.stale:
            logger.info(
                "profile_cas_conflict user_id=%s expected_revision=%s",
                user_id,
                expected_revision,
            )
            raise PreviewTokenError("STRATEGY_PREVIEW_STALE_PROFILE")

        saved_revision = int(result.revision or expected_revision + 1)
        logger.info(
            "conflict_resolved user_id=%s conflict_code=%s action=%s profile_revision=%s",
            user_id,
            detected.conflict.code,
            action,
            saved_revision,
        )
        return ResolveConflictResponse(
            status="resolved",
            profile_revision=saved_revision,
            requires_new_preview=True,
        )


def verify_resolution_context(
    *,
    token: str,
    user_id: int,
    profile: dict[str, object],
    profile_revision: int,
    memory_context: StrategyMemoryContext,
    behavior_context: StrategyBehaviorContext,
    memory_unavailable: bool,
    behavior_unavailable: bool,
) -> VerifiedPreviewToken:
    return verify_preview_token(
        token,
        user_id=user_id,
        profile=profile,
        profile_revision=profile_revision,
        memory_context=memory_context,
        behavior_context=behavior_context,
        memory_unavailable=memory_unavailable,
        behavior_unavailable=behavior_unavailable,
    )
