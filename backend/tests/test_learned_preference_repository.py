"""Repository: append-only lifecycle, content immutability, guarded transitions."""

from __future__ import annotations

import asyncio

import pytest

import config
import database
from learned_preferences.exceptions import (
    LearnedPreferenceNotAvailableError,
    LearnedPreferenceNotFoundError,
)
from learned_preferences.repository import (
    LearnedPreferenceRepository,
    preference_key,
)


@pytest.fixture
def repo(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATABASE_PATH", str(tmp_path / "lp-repo.db"))
    asyncio.run(database.init_db())
    return LearnedPreferenceRepository()


def _create(repo, **overrides):
    params = dict(
        user_id=42,
        preference_id=preference_key("prefer_familiar_meals"),
        preference_type="prefer_familiar_meals",
        source="decision_learning",
        evidence_json='{"source": "decision_learning", "confidence": "strong"}',
        preference_json='{"type": "prefer_familiar_meals"}',
        status="candidate",
    )
    params.update(overrides)
    return asyncio.run(repo.create(**params))


def test_create_then_get_and_list(repo):
    record = _create(repo)
    assert record.status == "candidate"
    assert record.created_at is not None
    fetched = asyncio.run(repo.get(42, record.id))
    assert fetched == record
    listed = asyncio.run(repo.list_for_user(42))
    assert [item.id for item in listed] == [record.id]


def test_active_creation_sets_accepted_at(repo):
    record = _create(repo, status="active")
    assert record.status == "active"
    assert record.accepted_at is not None
    assert record.revoked_at is None


def test_transition_preserves_content_columns(repo):
    created = _create(repo)
    activated = asyncio.run(
        repo.transition(
            user_id=42,
            preference_id=created.id,
            target_status="active",
            allowed_from=("candidate", "accepted"),
        )
    )
    assert activated.status == "active"
    assert activated.accepted_at is not None
    # Content is never rewritten.
    assert activated.type == created.type
    assert activated.source == created.source
    assert activated.version == created.version
    assert activated.evidence_json == created.evidence_json
    assert activated.preference_json == created.preference_json
    assert activated.created_at == created.created_at


def test_transition_rejects_disallowed_source_status(repo):
    created = _create(repo, status="revoked")
    with pytest.raises(LearnedPreferenceNotAvailableError):
        asyncio.run(
            repo.transition(
                user_id=42,
                preference_id=created.id,
                target_status="active",
                allowed_from=("candidate", "accepted"),
            )
        )


def test_transition_missing_row_raises_not_found(repo):
    with pytest.raises(LearnedPreferenceNotFoundError):
        asyncio.run(
            repo.transition(
                user_id=42,
                preference_id="v1:prefer_fast_meals",
                target_status="revoked",
                allowed_from=("candidate", "accepted", "active"),
            )
        )


def test_duplicate_create_is_not_available(repo):
    _create(repo)
    with pytest.raises(LearnedPreferenceNotAvailableError):
        _create(repo)


def test_ownership_is_scoped_by_user(repo):
    record = _create(repo)
    assert asyncio.run(repo.get(999, record.id)) is None
    assert asyncio.run(repo.list_for_user(999)) == []
