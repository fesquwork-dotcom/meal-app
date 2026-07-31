"""Profile persistence result types."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ProfileSaveResult:
    success: bool
    profile: dict[str, object] | None = None
    revision: int | None = None
    stale: bool = False
    current_profile: dict[str, object] | None = None
    current_revision: int | None = None
