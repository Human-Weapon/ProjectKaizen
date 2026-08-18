"""Stop-the-line policy layered on top of `models.AttemptBudget`.

`AttemptBudget` itself is a dumb counter (attempts_used vs max_attempts) —
appropriately generic, since it's reused wherever anything needs a bounded
retry count. This module adds the *hypothesis-aware* debugging discipline
on top of it without polluting that generic contract: repeatedly retrying
a fix under an unchanged root-cause hypothesis is a smell, not diligence.

    attempt 1 fails -> re-analyze evidence
    attempt 2 fails -> re-analyze AND reduce confidence in the hypothesis
    attempt 3 fails -> ARCHITECTURE_REVIEW_REQUIRED; attempt 4 is blocked

A blocked attempt can only reopen with one of: materially new evidence,
a materially changed root-cause hypothesis (different fingerprint), or an
explicit architecture-review override. Reopening is never silent — a caller
that discards this module's decision and retries anyway is not something
ProjectKaizen can prevent at the type level, but the policy itself never
manufactures permission on its own.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .exceptions import ValidationError
from .models import AttemptBudget
from .numbers import require_nonblank_str

#: attempts_used at or above this count requires an explicit reopening reason
ARCHITECTURE_REVIEW_THRESHOLD = 3


class AttemptGuidance(str, Enum):
    CONTINUE = "continue"
    REDUCE_CONFIDENCE = "reduce_confidence"
    ARCHITECTURE_REVIEW_REQUIRED = "architecture_review_required"
    REOPENED = "reopened"


@dataclass(frozen=True, slots=True)
class AttemptPolicyDecision:
    can_attempt: bool
    guidance: AttemptGuidance
    rationale: str


def evaluate_attempt_policy(
    *,
    budget: AttemptBudget,
    hypothesis_fingerprint: str,
    previous_hypothesis_fingerprint: str | None = None,
    new_evidence_since_last_attempt: bool = False,
    architecture_review_override: bool = False,
) -> AttemptPolicyDecision:
    hypothesis_fingerprint = require_nonblank_str(hypothesis_fingerprint, name="hypothesis_fingerprint")
    if not isinstance(budget, AttemptBudget):
        raise ValidationError("budget must be an AttemptBudget")

    hypothesis_changed = (
        previous_hypothesis_fingerprint is not None and previous_hypothesis_fingerprint != hypothesis_fingerprint
    )

    if budget.attempts_used < ARCHITECTURE_REVIEW_THRESHOLD:
        if budget.attempts_used == 0:
            return AttemptPolicyDecision(True, AttemptGuidance.CONTINUE, "first attempt")
        if budget.attempts_used == 1:
            return AttemptPolicyDecision(
                True, AttemptGuidance.CONTINUE, "attempt 1 failed; re-analyze evidence before retrying"
            )
        return AttemptPolicyDecision(
            True,
            AttemptGuidance.REDUCE_CONFIDENCE,
            "attempt 2 failed; re-analyze evidence and reduce confidence in the current hypothesis",
        )

    if new_evidence_since_last_attempt:
        return AttemptPolicyDecision(True, AttemptGuidance.REOPENED, "reopened: materially new evidence available")
    if hypothesis_changed:
        return AttemptPolicyDecision(
            True, AttemptGuidance.REOPENED, "reopened: root-cause hypothesis changed materially"
        )
    if architecture_review_override:
        return AttemptPolicyDecision(
            True, AttemptGuidance.REOPENED, "reopened: architecture decision explicitly allows continuation"
        )

    return AttemptPolicyDecision(
        False,
        AttemptGuidance.ARCHITECTURE_REVIEW_REQUIRED,
        f"{budget.attempts_used} failed attempt(s) under an unchanged hypothesis; "
        "blind retry is not permitted without new evidence, a changed hypothesis, or an explicit override",
    )
