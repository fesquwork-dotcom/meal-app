"""Domain exceptions for the Learned Preferences package."""

from __future__ import annotations


class LearnedPreferenceNotFoundError(Exception):
    """Preference/candidate does not exist or belongs to another user."""


class LearnedPreferenceNotAvailableError(Exception):
    """Lifecycle transition is not allowed from the current status."""


class LearnedPreferencePersistenceError(Exception):
    """Storage failure while reading or writing learned preference state."""
