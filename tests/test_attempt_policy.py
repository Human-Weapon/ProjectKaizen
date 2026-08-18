from __future__ import annotations

import pytest

from projectkaizen.attempt_policy import AttemptGuidance, evaluate_attempt_policy
from projectkaizen.exceptions import ValidationError
from projectkaizen.models import AttemptBudget


def _budget(attempts_used: int) -> AttemptBudget:
    return AttemptBudget(improvement_id="i1", max_attempts=10, attempts_used=attempts_used)


def test_first_attempt_continues():
    d = evaluate_attempt_policy(budget=_budget(0), hypothesis_fingerprint="h1")
    assert d.can_attempt is True
    assert d.guidance == AttemptGuidance.CONTINUE


def test_attempt_1_failure_continues():
    d = evaluate_attempt_policy(budget=_budget(1), hypothesis_fingerprint="h1")
    assert d.can_attempt is True
    assert d.guidance == AttemptGuidance.CONTINUE


def test_attempt_2_failure_reduces_confidence():
    d = evaluate_attempt_policy(budget=_budget(2), hypothesis_fingerprint="h1")
    assert d.can_attempt is True
    assert d.guidance == AttemptGuidance.REDUCE_CONFIDENCE


def test_attempt_3_failure_same_hypothesis_blocks():
    d = evaluate_attempt_policy(budget=_budget(3), hypothesis_fingerprint="h1", previous_hypothesis_fingerprint="h1")
    assert d.can_attempt is False
    assert d.guidance == AttemptGuidance.ARCHITECTURE_REVIEW_REQUIRED


def test_reopen_with_new_evidence():
    d = evaluate_attempt_policy(
        budget=_budget(3),
        hypothesis_fingerprint="h1",
        previous_hypothesis_fingerprint="h1",
        new_evidence_since_last_attempt=True,
    )
    assert d.can_attempt is True
    assert d.guidance == AttemptGuidance.REOPENED


def test_reopen_with_changed_hypothesis():
    d = evaluate_attempt_policy(budget=_budget(3), hypothesis_fingerprint="h2", previous_hypothesis_fingerprint="h1")
    assert d.can_attempt is True
    assert d.guidance == AttemptGuidance.REOPENED


def test_reopen_with_explicit_override():
    d = evaluate_attempt_policy(
        budget=_budget(3),
        hypothesis_fingerprint="h1",
        previous_hypothesis_fingerprint="h1",
        architecture_review_override=True,
    )
    assert d.can_attempt is True
    assert d.guidance == AttemptGuidance.REOPENED


def test_beyond_threshold_still_blocked_without_reopening_reason():
    d = evaluate_attempt_policy(budget=_budget(7), hypothesis_fingerprint="h1", previous_hypothesis_fingerprint="h1")
    assert d.can_attempt is False


def test_no_previous_hypothesis_at_threshold_is_not_a_change():
    # previous_hypothesis_fingerprint=None means "we don't know it changed" —
    # must not be silently treated as a change permitting reopening.
    d = evaluate_attempt_policy(budget=_budget(3), hypothesis_fingerprint="h1")
    assert d.can_attempt is False


def test_rejects_blank_hypothesis_fingerprint():
    with pytest.raises(ValidationError):
        evaluate_attempt_policy(budget=_budget(0), hypothesis_fingerprint="")


def test_rejects_non_attempt_budget():
    with pytest.raises(ValidationError):
        evaluate_attempt_policy(budget="not a budget", hypothesis_fingerprint="h1")  # type: ignore[arg-type]
