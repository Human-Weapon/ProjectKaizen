"""Domain exception hierarchy for ProjectKaizen."""

from __future__ import annotations


class ProjectKaizenError(Exception):
    """Base exception for all ProjectKaizen errors."""

    exit_code = 1


class ConfigurationError(ProjectKaizenError):
    """Invalid configuration or CLI usage."""

    exit_code = 2


class ValidationError(ProjectKaizenError):
    """A value failed domain validation (type, range, uniqueness)."""

    exit_code = 2


class PersistenceError(ProjectKaizenError):
    """Base for storage/IO persistence failures (domain-neutral)."""

    exit_code = 1


class CorruptStateError(PersistenceError):
    """Persisted JSON is syntactically or schematically invalid."""

    exit_code = 4

    def __init__(self, message: str, quarantined_path: str | None = None) -> None:
        super().__init__(message)
        self.quarantined_path = quarantined_path


class PathEscapeError(PersistenceError):
    """A resolved path escaped the configured root."""

    exit_code = 6


class VerificationError(ProjectKaizenError):
    """A configured verification command failed or timed out."""

    exit_code = 5


class IncompleteAnalysisError(ProjectKaizenError):
    """Analysis is incomplete and the caller configured that as failure."""

    exit_code = 3


class DuplicateError(ValidationError):
    """A graph or collection already contains this identifier."""

    exit_code = 2
