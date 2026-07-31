"""Deterministic preference conflict detection before strategy generation."""

from __future__ import annotations

from memory.constants import ConfirmationSource, SignalType
from shopping.normalization import canonical_ingredient_name, display_ingredient_name
from strategy.conflict_targets import (
    ConflictResolutionTarget,
    DetectedConflict,
    build_detected_conflict,
)
from strategy.context import ProfileContext
from strategy.effective_exclusions import (
    EffectiveExclusion,
    build_profile_exclusions,
    has_legacy_exclusions,
)
from strategy.memory_apply import PROTEIN_CANONICAL_KEYS, _protein_conflicts_with_avoid
from strategy.memory_context import MAX_MEMORY_AVOIDS_APPLIED, StrategyMemoryContext
from strategy.preview_models import (
    MAX_CONFLICTS_RETURNED,
    MAX_OPTIONS_PER_CONFLICT,
    ConflictResolutionAction,
    ConflictResolutionOption,
)

PREFERRED_PROTEIN_EXCLUDED_BY_MEMORY = "PREFERRED_PROTEIN_EXCLUDED_BY_MEMORY"
PREFERRED_PROTEIN_BLOCKED_BY_ALLERGY = "PREFERRED_PROTEIN_BLOCKED_BY_ALLERGY"
PREFERRED_PROTEIN_BLOCKED_BY_INTOLERANCE = "PREFERRED_PROTEIN_BLOCKED_BY_INTOLERANCE"
PREFERRED_PROTEIN_BLOCKED_BY_LEGACY_CONSTRAINT = "PREFERRED_PROTEIN_BLOCKED_BY_LEGACY_CONSTRAINT"
PREFERRED_PROTEIN_EXCLUDED_BY_PROFILE_PREFERENCE = (
    "PREFERRED_PROTEIN_EXCLUDED_BY_PROFILE_PREFERENCE"
)
LEGACY_CONSTRAINTS_REQUIRE_REVIEW = "LEGACY_CONSTRAINTS_REQUIRE_REVIEW"
TOO_MANY_MEMORY_EXCLUSIONS = "TOO_MANY_MEMORY_EXCLUSIONS"
NO_ALLOWED_PREFERRED_PROTEINS = "NO_ALLOWED_PREFERRED_PROTEINS"
EXPLICIT_COOKTIME_OVERRIDES_MEMORY = "EXPLICIT_COOKTIME_OVERRIDES_MEMORY"
MEMORY_SIGNAL_INVALID_TARGET = "MEMORY_SIGNAL_INVALID_TARGET"
MEMORY_AVOID_IGNORED_FOR_PROTEIN = "MEMORY_AVOID_IGNORED_FOR_PROTEIN"
PROTEIN_PARTIALLY_EXCLUDED = "PROTEIN_PARTIALLY_EXCLUDED"

SAFETY_BLOCK_CODES: dict[str, str] = {
    "profile_allergy": PREFERRED_PROTEIN_BLOCKED_BY_ALLERGY,
    "profile_intolerance": PREFERRED_PROTEIN_BLOCKED_BY_INTOLERANCE,
    "profile_legacy": PREFERRED_PROTEIN_BLOCKED_BY_LEGACY_CONSTRAINT,
}

SAFETY_SOURCE_LABELS: dict[str, str] = {
    "profile_allergy": "указана в аллергиях",
    "profile_intolerance": "указана в непереносимостях",
    "profile_legacy": "указана в старых исключениях профиля",
}

PROTEIN_LABELS: dict[str, str] = {
    "chicken": "курица",
    "beef": "говядина",
    "pork": "свинина",
    "fish": "рыба",
    "seafood": "морепродукты",
    "eggs": "яйца",
    "veggie": "овощи",
}

RESOLUTION_ACTIONS = frozenset(action.value for action in ConflictResolutionAction)

CONFLICT_ACTIONS: dict[str, frozenset[str]] = {
    PREFERRED_PROTEIN_EXCLUDED_BY_MEMORY: frozenset(
        {
            ConflictResolutionAction.DISMISS_MEMORY_SIGNAL.value,
            ConflictResolutionAction.REMOVE_PROFILE_PROTEIN.value,
        }
    ),
    # Safety conflicts never expose a constraint-removal action.
    PREFERRED_PROTEIN_BLOCKED_BY_ALLERGY: frozenset(
        {ConflictResolutionAction.REMOVE_PROFILE_PROTEIN.value}
    ),
    PREFERRED_PROTEIN_BLOCKED_BY_INTOLERANCE: frozenset(
        {ConflictResolutionAction.REMOVE_PROFILE_PROTEIN.value}
    ),
    PREFERRED_PROTEIN_BLOCKED_BY_LEGACY_CONSTRAINT: frozenset(
        {ConflictResolutionAction.REMOVE_PROFILE_PROTEIN.value}
    ),
    PREFERRED_PROTEIN_EXCLUDED_BY_PROFILE_PREFERENCE: frozenset(
        {
            ConflictResolutionAction.REMOVE_PROFILE_PROTEIN.value,
            ConflictResolutionAction.REMOVE_PROFILE_PREFERENCE.value,
        }
    ),
    LEGACY_CONSTRAINTS_REQUIRE_REVIEW: frozenset(),
    TOO_MANY_MEMORY_EXCLUSIONS: frozenset(),
    NO_ALLOWED_PREFERRED_PROTEINS: frozenset(
        {ConflictResolutionAction.REMOVE_PROFILE_PROTEIN.value}
    ),
    EXPLICIT_COOKTIME_OVERRIDES_MEMORY: frozenset(),
    MEMORY_SIGNAL_INVALID_TARGET: frozenset(
        {ConflictResolutionAction.DISMISS_MEMORY_SIGNAL.value}
    ),
    MEMORY_AVOID_IGNORED_FOR_PROTEIN: frozenset(
        {ConflictResolutionAction.DISMISS_MEMORY_SIGNAL.value}
    ),
}

CONFLICT_PRIORITIES: dict[str, int] = {
    TOO_MANY_MEMORY_EXCLUSIONS: 5,
    PREFERRED_PROTEIN_BLOCKED_BY_ALLERGY: 8,
    PREFERRED_PROTEIN_BLOCKED_BY_INTOLERANCE: 9,
    PREFERRED_PROTEIN_BLOCKED_BY_LEGACY_CONSTRAINT: 10,
    PREFERRED_PROTEIN_EXCLUDED_BY_PROFILE_PREFERENCE: 12,
    NO_ALLOWED_PREFERRED_PROTEINS: 15,
    PREFERRED_PROTEIN_EXCLUDED_BY_MEMORY: 20,
    PROTEIN_PARTIALLY_EXCLUDED: 50,
    MEMORY_SIGNAL_INVALID_TARGET: 65,
    MEMORY_AVOID_IGNORED_FOR_PROTEIN: 60,
    EXPLICIT_COOKTIME_OVERRIDES_MEMORY: 70,
    LEGACY_CONSTRAINTS_REQUIRE_REVIEW: 75,
    "MEMORY_CONTEXT_UNAVAILABLE": 80,
}


def _protein_label(protein: str) -> str:
    return PROTEIN_LABELS.get(protein, protein)


def _explicit_proteins(context: ProfileContext) -> list[str]:
    if not context.proteins_explicit or context.proteins == ["any"]:
        return []
    return list(context.proteins)


def _protein_canonical(protein: str) -> str:
    return canonical_ingredient_name(PROTEIN_CANONICAL_KEYS.get(protein, protein))


def _limit_conflicts(items: list[DetectedConflict]) -> list[DetectedConflict]:
    sorted_items = sorted(items, key=lambda item: (item.priority, item.conflict_id))
    limited: list[DetectedConflict] = []
    for item in sorted_items[:MAX_CONFLICTS_RETURNED]:
        options = item.conflict.options[:MAX_OPTIONS_PER_CONFLICT]
        limited.append(
            DetectedConflict(
                conflict_id=item.conflict_id,
                conflict=item.conflict.model_copy(update={"options": options}),
                target=item.target,
                priority=item.priority,
            )
        )
    return limited


def _build_protein_exclusion_conflict(
    profile_context: ProfileContext,
    *,
    protein: str,
    exclusion: EffectiveExclusion,
    profile_revision: int,
    preview_version: int,
) -> DetectedConflict:
    """Kind-aware blocking conflict for a preferred protein excluded by profile."""
    label = _protein_label(protein)

    if exclusion.source in SAFETY_BLOCK_CODES:
        code = SAFETY_BLOCK_CODES[exclusion.source]
        source_label = SAFETY_SOURCE_LABELS[exclusion.source]
        return build_detected_conflict(
            code=code,
            title="Белок исключён ограничением",
            description=(
                f"{label.capitalize()} выбрана как предпочтительный белок, но {source_label}. "
                "Чтобы продолжить, выберите другой белок в профиле."
            ),
            severity="blocking",
            field="proteins",
            options=[
                ConflictResolutionOption(
                    action=ConflictResolutionAction.REMOVE_PROFILE_PROTEIN.value,
                    label="Изменить белки",
                    description=f"Убрать {label} из предпочтительных белков.",
                ),
            ],
            target=ConflictResolutionTarget(
                profile_field="proteins",
                canonical_value=protein,
                exclusion_value=exclusion.display_value,
            ),
            profile_revision=profile_revision,
            preview_version=preview_version,
            priority=CONFLICT_PRIORITIES[code],
        )

    constraint_id = next(
        (
            constraint.id
            for constraint in profile_context.dietary_constraints
            if constraint.canonical_value == exclusion.canonical_value
        ),
        None,
    )
    return build_detected_conflict(
        code=PREFERRED_PROTEIN_EXCLUDED_BY_PROFILE_PREFERENCE,
        title="Нужно уточнить предпочтение",
        description=(
            f"{label.capitalize()} одновременно выбрана как предпочтительный белок "
            f"и указана во вкусовых исключениях профиля."
        ),
        severity="blocking",
        field="proteins",
        options=[
            ConflictResolutionOption(
                action=ConflictResolutionAction.REMOVE_PROFILE_PROTEIN.value,
                label=f"Не предлагать {label}",
                description="Убрать продукт из предпочтительных белков.",
            ),
            ConflictResolutionOption(
                action=ConflictResolutionAction.REMOVE_PROFILE_PREFERENCE.value,
                label=f"Разрешить {label}",
                description="Убрать продукт из вкусовых исключений профиля.",
            ),
        ],
        target=ConflictResolutionTarget(
            profile_field="proteins",
            canonical_value=protein,
            exclusion_value=exclusion.display_value,
            constraint_id=constraint_id,
        ),
        profile_revision=profile_revision,
        preview_version=preview_version,
        priority=CONFLICT_PRIORITIES[PREFERRED_PROTEIN_EXCLUDED_BY_PROFILE_PREFERENCE],
    )


def detect_strategy_conflicts(
    profile_context: ProfileContext,
    memory_context: StrategyMemoryContext,
    *,
    profile_revision: int = 0,
    preview_version: int = 1,
) -> tuple[list[DetectedConflict], list[DetectedConflict]]:
    """Returns (blocking_conflicts, warnings). Pure and deterministic."""
    blocking: list[DetectedConflict] = []
    warnings: list[DetectedConflict] = []

    explicit_proteins = _explicit_proteins(profile_context)
    effective_exclusions = build_profile_exclusions(profile_context)
    profile_exclusions = {item.canonical_value for item in effective_exclusions}

    avoid_signals = [
        signal
        for signal in memory_context.signals
        if signal.signal_type == SignalType.AVOID_INGREDIENT.value
    ]

    if len(avoid_signals) > MAX_MEMORY_AVOIDS_APPLIED:
        blocking.append(
            build_detected_conflict(
                code=TOO_MANY_MEMORY_EXCLUSIONS,
                title="Слишком много исключений",
                description=(
                    "Сохранено слишком много исключений для автоматического построения меню. "
                    "Проверьте раздел «Приложение запомнило»."
                ),
                severity="blocking",
                field="memory",
                options=[],
                target=ConflictResolutionTarget(profile_field="memory"),
                profile_revision=profile_revision,
                preview_version=preview_version,
                priority=CONFLICT_PRIORITIES[TOO_MANY_MEMORY_EXCLUSIONS],
            )
        )
        return _limit_conflicts(blocking), _limit_conflicts(warnings)

    for protein in explicit_proteins:
        canonical = _protein_canonical(protein)
        exclusion = next(
            (item for item in effective_exclusions if item.canonical_value == canonical),
            None,
        )
        if exclusion is None:
            continue
        blocking.append(
            _build_protein_exclusion_conflict(
                profile_context,
                protein=protein,
                exclusion=exclusion,
                profile_revision=profile_revision,
                preview_version=preview_version,
            )
        )

    user_confirmed_avoids: list[tuple[object, str]] = []
    automatic_conflicts: list[tuple[object, str, str]] = []
    invalid_targets: list[object] = []
    applicable_avoids: list[str] = []

    for signal in avoid_signals:
        target = signal.target_value.strip()
        if not target:
            invalid_targets.append(signal)
            continue

        conflicting = [
            protein
            for protein in explicit_proteins
            if _protein_conflicts_with_avoid(protein, target)
        ]
        if not conflicting:
            applicable_avoids.append(target)
            continue

        label = display_ingredient_name(target)
        remaining_after_conflict = [
            protein
            for protein in explicit_proteins
            if protein not in conflicting
        ]

        if remaining_after_conflict:
            applicable_avoids.append(target)
            excluded_names = [_protein_label(protein) for protein in conflicting]
            remaining_names = [_protein_label(protein) for protein in remaining_after_conflict]
            warnings.append(
                build_detected_conflict(
                    code=PROTEIN_PARTIALLY_EXCLUDED,
                    title="Часть белков исключена",
                    description=(
                        f"{', '.join(excluded_names).capitalize()} исключена, "
                        f"{', '.join(remaining_names)} останется в ротации."
                    ),
                    severity="warning",
                    field="proteins",
                    options=[
                        ConflictResolutionOption(
                            action="continue_with_warning",
                            label="Продолжить",
                            description=None,
                        )
                    ],
                    target=ConflictResolutionTarget(
                        profile_field="proteins",
                        canonical_value=conflicting[0],
                        memory_signal_id=signal.signal_id,
                    ),
                    profile_revision=profile_revision,
                    preview_version=preview_version,
                    priority=CONFLICT_PRIORITIES[PROTEIN_PARTIALLY_EXCLUDED],
                )
            )
            continue

        if signal.confirmation_source == ConfirmationSource.USER.value and explicit_proteins:
            user_confirmed_avoids.append((signal, label))
        elif explicit_proteins:
            automatic_conflicts.append((signal, label, conflicting[0]))

    for signal, label in user_confirmed_avoids:
        protein_code = next(
            (
                protein
                for protein in explicit_proteins
                if _protein_conflicts_with_avoid(protein, signal.target_value.strip())
            ),
            explicit_proteins[0],
        )
        protein_label = _protein_label(protein_code)
        blocking.append(
            build_detected_conflict(
                code=PREFERRED_PROTEIN_EXCLUDED_BY_MEMORY,
                title="Нужно уточнить предпочтение",
                description=(
                    f"{protein_label.capitalize()} одновременно выбрана как предпочтительный белок "
                    f"и отмечена как продукт, который не нужно предлагать."
                ),
                severity="blocking",
                field="proteins",
                options=[
                    ConflictResolutionOption(
                        action=ConflictResolutionAction.DISMISS_MEMORY_SIGNAL.value,
                        label=f"Оставить {protein_label}",
                        description="Запомненное исключение будет удалено.",
                    ),
                    ConflictResolutionOption(
                        action=ConflictResolutionAction.REMOVE_PROFILE_PROTEIN.value,
                        label=f"Не предлагать {label.lower()}",
                        description=f"Убрать {protein_label} из предпочтительных белков.",
                    ),
                ],
                target=ConflictResolutionTarget(
                    profile_field="proteins",
                    canonical_value=protein_code,
                    memory_signal_id=signal.signal_id,
                ),
                profile_revision=profile_revision,
                preview_version=preview_version,
                priority=CONFLICT_PRIORITIES[PREFERRED_PROTEIN_EXCLUDED_BY_MEMORY],
            )
        )

    for signal, label, protein_code in automatic_conflicts:
        protein_label = _protein_label(protein_code)
        warnings.append(
            build_detected_conflict(
                code=MEMORY_AVOID_IGNORED_FOR_PROTEIN,
                title="Предпочтение профиля важнее",
                description=(
                    f"В профиле выбрана {protein_label}, поэтому запомненное исключение "
                    f"«{label}» не будет применено к следующему плану."
                ),
                severity="warning",
                field="memory",
                options=[
                    ConflictResolutionOption(
                        action=ConflictResolutionAction.DISMISS_MEMORY_SIGNAL.value,
                        label="Удалить запомненное исключение",
                        description="Исключение больше не будет учитываться.",
                    ),
                    ConflictResolutionOption(
                        action="continue_with_warning",
                        label="Продолжить",
                        description="План будет создан с учётом профиля.",
                    ),
                ],
                target=ConflictResolutionTarget(
                    profile_field="memory",
                    memory_signal_id=signal.signal_id,
                    canonical_value=protein_code,
                ),
                profile_revision=profile_revision,
                preview_version=preview_version,
                priority=CONFLICT_PRIORITIES[MEMORY_AVOID_IGNORED_FOR_PROTEIN],
            )
        )

    if explicit_proteins:
        remaining = [
            protein
            for protein in explicit_proteins
            if not any(_protein_conflicts_with_avoid(protein, avoid) for avoid in applicable_avoids)
            and canonical_ingredient_name(PROTEIN_CANONICAL_KEYS.get(protein, protein))
            not in profile_exclusions
        ]
        if explicit_proteins and not remaining and not user_confirmed_avoids:
            blocking.append(
                build_detected_conflict(
                    code=NO_ALLOWED_PREFERRED_PROTEINS,
                    title="Нет допустимых белков",
                    description=(
                        "После учёта исключений не остаётся предпочтительных белков для плана."
                    ),
                    severity="blocking",
                    field="proteins",
                    options=[
                        ConflictResolutionOption(
                            action=ConflictResolutionAction.REMOVE_PROFILE_PROTEIN.value,
                            label="Изменить белки в профиле",
                            description="Выберите другие предпочтительные белки.",
                        ),
                    ],
                    target=ConflictResolutionTarget(profile_field="proteins"),
                    profile_revision=profile_revision,
                    preview_version=preview_version,
                    priority=CONFLICT_PRIORITIES[NO_ALLOWED_PREFERRED_PROTEINS],
                )
            )

    for signal in invalid_targets:
        warnings.append(
            build_detected_conflict(
                code=MEMORY_SIGNAL_INVALID_TARGET,
                title="Некорректное предпочтение",
                description="Одно из запомненных предпочтений не может быть применено.",
                severity="warning",
                field="memory",
                options=[
                    ConflictResolutionOption(
                        action=ConflictResolutionAction.DISMISS_MEMORY_SIGNAL.value,
                        label="Удалить предпочтение",
                        description=None,
                    ),
                    ConflictResolutionOption(
                        action="continue_with_warning",
                        label="Продолжить",
                        description=None,
                    ),
                ],
                target=ConflictResolutionTarget(
                    profile_field="memory",
                    memory_signal_id=signal.signal_id,
                ),
                profile_revision=profile_revision,
                preview_version=preview_version,
                priority=CONFLICT_PRIORITIES[MEMORY_SIGNAL_INVALID_TARGET],
            )
        )

    if has_legacy_exclusions(profile_context):
        warnings.append(
            build_detected_conflict(
                code=LEGACY_CONSTRAINTS_REQUIRE_REVIEW,
                title="Проверьте старые исключения",
                description=(
                    "В профиле остались исключения без указанного типа. "
                    "Они по-прежнему полностью исключаются из меню. "
                    "Уточните их тип в настройках профиля."
                ),
                severity="warning",
                field="dietary_constraints",
                options=[
                    ConflictResolutionOption(
                        action="continue_with_warning",
                        label="Продолжить",
                        description="Старые исключения останутся исключёнными.",
                    ),
                ],
                target=ConflictResolutionTarget(profile_field="dietary_constraints"),
                profile_revision=profile_revision,
                preview_version=preview_version,
                priority=CONFLICT_PRIORITIES[LEGACY_CONSTRAINTS_REQUIRE_REVIEW],
            )
        )

    return _limit_conflicts(blocking), _limit_conflicts(warnings)


def find_detected_conflict(
    conflicts: list[DetectedConflict],
    warnings: list[DetectedConflict],
    conflict_id: str,
) -> DetectedConflict | None:
    for item in [*conflicts, *warnings]:
        if item.conflict_id == conflict_id:
            return item
    return None


def is_action_allowed(conflict_code: str, action: str) -> bool:
    if action not in RESOLUTION_ACTIONS:
        return False
    allowed = CONFLICT_ACTIONS.get(conflict_code)
    if allowed is None:
        return False
    return action in allowed
