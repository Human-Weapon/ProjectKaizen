from __future__ import annotations

from projectkaizen import human
from projectkaizen.models import ComparisonVerdict, StoppingReason, ViabilityStatus
from projectkaizen.release.models import ChangeCategory, ReadinessOutcome, ReleaseFindingStatus


def test_every_viability_status_has_plain_text():
    for status in ViabilityStatus:
        text = human.plain_viability(status)
        assert text and status.value not in text


def test_every_stopping_reason_has_plain_text():
    for reason in StoppingReason:
        text = human.plain_stopping_reason(reason)
        assert text and reason.value not in text


def test_plain_stopping_reasons_joins_multiple():
    text = human.plain_stopping_reasons((StoppingReason.NO_RELEVANT_FINDINGS, StoppingReason.MARGINAL_ONLY))
    assert "; " in text


def test_plain_stopping_reasons_empty_tuple():
    assert human.plain_stopping_reasons(()) == ""


def test_every_verdict_has_plain_text():
    for verdict in ComparisonVerdict:
        text = human.plain_verdict(verdict)
        assert text


def test_every_readiness_outcome_has_plain_text():
    for outcome in ReadinessOutcome:
        text = human.plain_readiness_outcome(outcome)
        assert text


def test_no_blocker_found_never_reads_as_unqualified_safe():
    # "guaranteed"/"safe" may appear only inside an explicit negation
    # ("does not mean ... guaranteed safe") — never as a bare claim.
    text = human.plain_readiness_outcome(ReadinessOutcome.NO_BLOCKER_FOUND).lower()
    assert "does not mean" in text
    assert "guaranteed safe" in text


def test_every_finding_status_has_plain_text():
    for status in ReleaseFindingStatus:
        text = human.plain_finding_status(status)
        assert text


def test_every_change_category_has_plain_text():
    for category in ChangeCategory:
        text = human.plain_change_category(category)
        assert text
