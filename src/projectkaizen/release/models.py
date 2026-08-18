"""Domain models for release readiness.

Mirrors the rest of ProjectKaizen's contract style: frozen dataclasses,
explicit enums, no ambiguous states. The one release-specific principle
worth stating up front: a changed file is *discovery evidence*, never a
finding by itself (spec section 17) — turning every diff line into a
"finding" would just be `git diff` with extra ceremony.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from ..exceptions import ValidationError
from ..models import Confidence
from ..numbers import require_nonblank_str, require_str_tuple


class ChangeCategory(str, Enum):
    PUBLIC_API = "public_api"
    CONFIG = "config"
    ENV_VARS = "env_vars"
    PERSISTED_SCHEMA = "persisted_schema"
    PACKAGE_METADATA = "package_metadata"
    PYTHON_SUPPORT = "python_support"
    DEPENDENCIES = "dependencies"
    CLI_CONTRACT = "cli_contract"
    ERROR_BEHAVIOR = "error_behavior"
    CONCURRENCY_LIFECYCLE = "concurrency_lifecycle"
    ARTIFACTS = "artifacts"
    MIGRATIONS = "migrations"
    COMPATIBILITY = "compatibility"
    OTHER = "other"


class ChangeType(str, Enum):
    ADDED = "added"
    MODIFIED = "modified"
    DELETED = "deleted"
    RENAMED = "renamed"


@dataclass(frozen=True, slots=True)
class ReleaseRef:
    ref: str
    sha: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "ref", require_nonblank_str(self.ref, name="release_ref.ref"))
        object.__setattr__(self, "sha", require_nonblank_str(self.sha, name="release_ref.sha"))


class ScopeConfidence(str, Enum):
    """Distinct from `models.Confidence` — this is about how *trustworthy the
    scope resolution itself* is (did we find a real base to diff against),
    not about a finding's confidence."""

    EXPLICIT = "explicit"  # caller supplied both refs directly
    RESOLVED_TAG = "resolved_tag"  # base was the latest usable tag
    NO_BASELINE = "no_baseline"  # no usable base found; never invented one


@dataclass(frozen=True, slots=True)
class ReleaseScope:
    base: ReleaseRef | None
    target: ReleaseRef
    dirty_worktree: bool
    confidence: ScopeConfidence
    rationale: str

    def __post_init__(self) -> None:
        if self.base is not None and not isinstance(self.base, ReleaseRef):
            raise ValidationError("release_scope.base must be a ReleaseRef or None")
        if not isinstance(self.target, ReleaseRef):
            raise ValidationError("release_scope.target must be a ReleaseRef")
        if not isinstance(self.dirty_worktree, bool):
            raise ValidationError("release_scope.dirty_worktree must be a bool")
        if not isinstance(self.confidence, ScopeConfidence):
            raise ValidationError("release_scope.confidence must be a ScopeConfidence")
        if self.confidence == ScopeConfidence.NO_BASELINE and self.base is not None:
            raise ValidationError("release_scope.confidence=NO_BASELINE requires base=None")
        if self.confidence != ScopeConfidence.NO_BASELINE and self.base is None:
            raise ValidationError("release_scope.base is required unless confidence=NO_BASELINE")
        object.__setattr__(self, "rationale", require_nonblank_str(self.rationale, name="release_scope.rationale"))


@dataclass(frozen=True, slots=True)
class ChangedFile:
    path: str
    change_type: ChangeType
    categories: tuple[ChangeCategory, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "path", require_nonblank_str(self.path, name="changed_file.path"))
        if not isinstance(self.change_type, ChangeType):
            raise ValidationError("changed_file.change_type must be a ChangeType")
        if not isinstance(self.categories, tuple) or not all(isinstance(c, ChangeCategory) for c in self.categories):
            raise ValidationError("changed_file.categories must be a tuple of ChangeCategory")


class ReleaseFindingStatus(str, Enum):
    BLOCKED = "blocked"
    NEEDS_CONFIRMATION = "needs_confirmation"
    UNABLE_TO_VERIFY = "unable_to_verify"
    NO_BLOCKER_FOUND = "no_blocker_found"


@dataclass(frozen=True, slots=True)
class ReleaseFinding:
    id: str
    category: ChangeCategory
    title: str
    description: str
    status: ReleaseFindingStatus
    evidence: tuple[str, ...] = ()
    affected_paths: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", require_nonblank_str(self.id, name="release_finding.id"))
        if not isinstance(self.category, ChangeCategory):
            raise ValidationError("release_finding.category must be a ChangeCategory")
        object.__setattr__(self, "title", require_nonblank_str(self.title, name="release_finding.title"))
        object.__setattr__(
            self, "description", require_nonblank_str(self.description, name="release_finding.description")
        )
        if not isinstance(self.status, ReleaseFindingStatus):
            raise ValidationError("release_finding.status must be a ReleaseFindingStatus")
        object.__setattr__(self, "evidence", require_str_tuple(self.evidence, name="release_finding.evidence"))
        object.__setattr__(
            self, "affected_paths", require_str_tuple(self.affected_paths, name="release_finding.affected_paths")
        )


class ReadinessOutcome(str, Enum):
    BLOCKED = "blocked"
    NEEDS_CONFIRMATION = "needs_confirmation"
    NO_BLOCKER_FOUND = "no_blocker_found"


@dataclass(frozen=True, slots=True)
class ReadinessReport:
    scope: ReleaseScope
    changed_file_count: int
    findings: tuple[ReleaseFinding, ...]
    outcome: ReadinessOutcome
    rationale: str
    confidence: Confidence

    def __post_init__(self) -> None:
        if not isinstance(self.scope, ReleaseScope):
            raise ValidationError("readiness_report.scope must be a ReleaseScope")
        if not isinstance(self.changed_file_count, int) or self.changed_file_count < 0:
            raise ValidationError("readiness_report.changed_file_count must be a non-negative int")
        if not isinstance(self.outcome, ReadinessOutcome):
            raise ValidationError("readiness_report.outcome must be a ReadinessOutcome")
        object.__setattr__(self, "rationale", require_nonblank_str(self.rationale, name="readiness_report.rationale"))
        if not isinstance(self.confidence, Confidence):
            raise ValidationError("readiness_report.confidence must be a Confidence")
