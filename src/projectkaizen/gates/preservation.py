"""The Preservation Gate: not understanding why code exists is not evidence
that it is unnecessary.

Before recommending a destructive simplification or removal, this gate
requires deterministic evidence about callers, tests, ADRs/project
guidance, recent git activity, and hard constraints (compatibility,
platform-specific behavior, performance). It never uses semantic/LLM
reasoning — only conservative rules over evidence the caller supplies.
Any unexamined field is treated as "unknown," never as "safe."
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from ..exceptions import ValidationError
from ..numbers import require_nonblank_str, require_str_tuple


class PreservationDecision(str, Enum):
    SAFE_TO_CHANGE = "safe_to_change"
    REQUIRES_MORE_CONTEXT = "requires_more_context"
    INTENT_STILL_VALID = "intent_still_valid"
    DO_NOT_REMOVE = "do_not_remove"


@dataclass(frozen=True, slots=True)
class PreservationEvidence:
    target_description: str
    #: number of call sites found, or None if callers were never searched for
    caller_count: int | None = None
    has_tests: bool | None = None
    referenced_by_adr: bool | None = None
    referenced_by_project_guidance: bool | None = None
    recent_git_activity: bool | None = None
    compatibility_constraint: bool | None = None
    platform_specific: bool | None = None
    performance_constraint: bool | None = None
    evidence_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "target_description", require_nonblank_str(self.target_description, name="preservation.target")
        )
        if self.caller_count is not None and (not isinstance(self.caller_count, int) or self.caller_count < 0):
            raise ValidationError("preservation.caller_count must be a non-negative int or None")
        for field_name in (
            "has_tests",
            "referenced_by_adr",
            "referenced_by_project_guidance",
            "recent_git_activity",
            "compatibility_constraint",
            "platform_specific",
            "performance_constraint",
        ):
            value = getattr(self, field_name)
            if value is not None and not isinstance(value, bool):
                raise ValidationError(f"preservation.{field_name} must be a bool or None")
        object.__setattr__(self, "evidence_ids", require_str_tuple(self.evidence_ids, name="preservation.evidence_ids"))


_HARD_CONSTRAINT_FIELDS = ("compatibility_constraint", "platform_specific", "performance_constraint")
_ALL_TRACKED_FIELDS = (
    "caller_count",
    "has_tests",
    "referenced_by_adr",
    "referenced_by_project_guidance",
    "recent_git_activity",
    "compatibility_constraint",
    "platform_specific",
    "performance_constraint",
)


@dataclass(frozen=True, slots=True)
class PreservationResult:
    decision: PreservationDecision
    rationale: str


def evaluate_preservation(evidence: PreservationEvidence) -> PreservationResult:
    hard_hits = [name for name in _HARD_CONSTRAINT_FIELDS if getattr(evidence, name) is True]
    if hard_hits:
        return PreservationResult(
            decision=PreservationDecision.DO_NOT_REMOVE,
            rationale=f"hard constraint(s) present: {', '.join(hard_hits)}",
        )

    unknown_fields = [name for name in _ALL_TRACKED_FIELDS if getattr(evidence, name) is None]
    if unknown_fields:
        return PreservationResult(
            decision=PreservationDecision.REQUIRES_MORE_CONTEXT,
            rationale=f"not yet investigated: {', '.join(unknown_fields)}; unknown is never treated as safe",
        )

    if evidence.referenced_by_adr or evidence.referenced_by_project_guidance:
        source = "an ADR" if evidence.referenced_by_adr else "project guidance"
        return PreservationResult(
            decision=PreservationDecision.INTENT_STILL_VALID,
            rationale=f"documented in {source} and nothing indicates that reason has expired",
        )

    if evidence.caller_count == 0:
        return PreservationResult(
            decision=PreservationDecision.SAFE_TO_CHANGE,
            rationale="no callers, no ADR/guidance reference, no hard constraints, all evidence gathered",
        )

    return PreservationResult(
        decision=PreservationDecision.REQUIRES_MORE_CONTEXT,
        rationale=f"{evidence.caller_count} caller(s) exist; inspect them before removing",
    )
