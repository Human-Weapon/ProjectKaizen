from __future__ import annotations

import pytest

from projectkaizen.exceptions import ValidationError
from projectkaizen.models import (
    AnalysisResult,
    AnalysisStatus,
    AttemptBudget,
    Baseline,
    Candidate,
    Confidence,
    Evidence,
    Finding,
    ImprovementStatus,
    ImprovementViability,
    OutputBudget,
    RootCause,
    RootCauseStatus,
    Severity,
    StoppingDecision,
    StoppingReason,
    ViabilityStatus,
    confidence_weight,
    severity_rank,
    validate_transition,
)


def test_severity_rank_ordering():
    assert severity_rank(Severity.CRITICAL) < severity_rank(Severity.HIGH) < severity_rank(Severity.LOW)


def test_confidence_weight_ordering():
    assert confidence_weight(Confidence.HIGH) > confidence_weight(Confidence.MEDIUM) > confidence_weight(Confidence.LOW)


def test_evidence_requires_nonblank_fields():
    Evidence(id="e1", kind="k", description="d", source="s")
    with pytest.raises(ValidationError):
        Evidence(id="", kind="k", description="d", source="s")


def test_finding_requires_tuple_evidence():
    with pytest.raises(ValidationError):
        Finding(
            id="f1",
            project_area_id="pa",
            title="t",
            description="d",
            evidence=[],  # not a tuple
            severity=Severity.LOW,
            confidence=Confidence.LOW,
        )


def test_root_cause_status_enum_enforced():
    RootCause(id="rc1", finding_id="f1", description="d", status=RootCauseStatus.CONFIRMED)
    with pytest.raises(ValidationError):
        RootCause(id="rc1", finding_id="f1", description="d", status="confirmed")


def test_baseline_requires_nonempty_finite_metrics():
    Baseline(id="b1", metrics={"latency": 1.0}, captured_from="run")
    with pytest.raises(ValidationError):
        Baseline(id="b1", metrics={}, captured_from="run")
    with pytest.raises(ValidationError):
        Baseline(id="b1", metrics={"latency": float("nan")}, captured_from="run")


def test_candidate_requires_nonempty_finite_metrics():
    Candidate(id="c1", baseline_id="b1", improvement_id="i1", metrics={"latency": 1.0}, captured_from="run")
    with pytest.raises(ValidationError):
        Candidate(id="c1", baseline_id="b1", improvement_id="i1", metrics={}, captured_from="run")


def test_improvement_viability_requires_rationale():
    with pytest.raises(ValidationError):
        ImprovementViability(status=ViabilityStatus.VIABLE, rationale="")


def test_attempt_budget_exhausted_and_remaining():
    budget = AttemptBudget(improvement_id="i1", max_attempts=3, attempts_used=2)
    assert budget.exhausted is False
    assert budget.remaining == 1
    next_budget = budget.with_attempt()
    assert next_budget.attempts_used == 3
    assert next_budget.exhausted is True
    assert next_budget.remaining == 0


def test_attempt_budget_rejects_invalid_values():
    with pytest.raises(ValidationError):
        AttemptBudget(improvement_id="i1", max_attempts=0)
    with pytest.raises(ValidationError):
        AttemptBudget(improvement_id="i1", max_attempts=3, attempts_used=-1)


def test_output_budget_rejects_bool_and_nonpositive():
    OutputBudget(max_findings_shown=5)
    with pytest.raises(ValidationError):
        OutputBudget(max_findings_shown=True)
    with pytest.raises(ValidationError):
        OutputBudget(max_findings_shown=0)


def test_analysis_result_incomplete_requires_reasons():
    AnalysisResult(analyzer="a", status=AnalysisStatus.COMPLETE, findings=())
    with pytest.raises(ValidationError):
        AnalysisResult(analyzer="a", status=AnalysisStatus.ANALYSIS_INCOMPLETE, findings=())
    AnalysisResult(analyzer="a", status=AnalysisStatus.ANALYSIS_INCOMPLETE, findings=(), incomplete_reasons=("x",))


def test_stopping_decision_requires_reasons_when_stable():
    with pytest.raises(ValidationError):
        StoppingDecision(stable=True, reasons=(), rationale="r")
    StoppingDecision(stable=True, reasons=(StoppingReason.NO_RELEVANT_FINDINGS,), rationale="r")
    StoppingDecision(stable=False, reasons=(), rationale="r")


def test_improvement_lifecycle_valid_transitions():
    validate_transition(ImprovementStatus.DISCOVERED, ImprovementStatus.UNDER_ANALYSIS)
    validate_transition(ImprovementStatus.VIABILITY_REVIEW, ImprovementStatus.READY)
    validate_transition(ImprovementStatus.VERIFYING, ImprovementStatus.ACCEPTED)


def test_improvement_lifecycle_invalid_transition_raises():
    with pytest.raises(ValidationError):
        validate_transition(ImprovementStatus.DISCOVERED, ImprovementStatus.ACCEPTED)
    with pytest.raises(ValidationError):
        validate_transition(ImprovementStatus.ACCEPTED, ImprovementStatus.REJECTED)


def test_terminal_states_can_still_be_superseded():
    validate_transition(ImprovementStatus.ACCEPTED, ImprovementStatus.SUPERSEDED)
    validate_transition(ImprovementStatus.REJECTED, ImprovementStatus.SUPERSEDED)


def test_deferred_and_inconclusive_can_reopen_to_under_analysis():
    validate_transition(ImprovementStatus.DEFERRED, ImprovementStatus.UNDER_ANALYSIS)
    validate_transition(ImprovementStatus.INCONCLUSIVE, ImprovementStatus.UNDER_ANALYSIS)


def test_non_terminal_state_can_also_be_superseded():
    validate_transition(ImprovementStatus.IN_PROGRESS, ImprovementStatus.SUPERSEDED)
    validate_transition(ImprovementStatus.DISCOVERED, ImprovementStatus.SUPERSEDED)


def test_superseded_cannot_be_superseded_again():
    with pytest.raises(ValidationError):
        validate_transition(ImprovementStatus.SUPERSEDED, ImprovementStatus.SUPERSEDED)
