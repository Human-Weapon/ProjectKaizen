from __future__ import annotations

import pytest

from projectkaizen.exceptions import ValidationError
from projectkaizen.models import (
    Comparison,
    ComparisonVerdict,
    Improvement,
    ImprovementOutcome,
    ImprovementStatus,
    Lesson,
    MetricDelta,
    VerificationPlan,
    VerificationResult,
)


def _plan(**overrides) -> VerificationPlan:
    kwargs = dict(  # noqa: C408
        id="vp1",
        description="run tests",
        commands=(("pytest",),),
        success_criteria="exit code 0",
    )
    kwargs.update(overrides)
    return VerificationPlan(**kwargs)


def test_verification_plan_requires_tuple_of_tuples():
    _plan()
    with pytest.raises(ValidationError):
        _plan(commands=[["pytest"]])  # not a tuple of tuples
    with pytest.raises(ValidationError):
        _plan(commands=((),))  # empty argv
    with pytest.raises(ValidationError):
        _plan(commands=(("",),))  # empty string entry
    with pytest.raises(ValidationError):
        _plan(commands=((1, 2),))  # non-string entries


def test_verification_plan_requires_nonblank_description_and_criteria():
    with pytest.raises(ValidationError):
        _plan(description="")
    with pytest.raises(ValidationError):
        _plan(success_criteria="")


def test_verification_result_requires_valid_types():
    VerificationResult(plan_id="p1", passed=True, exit_code=0, duration_seconds=1.0)
    with pytest.raises(ValidationError):
        VerificationResult(plan_id="", passed=True, exit_code=0, duration_seconds=1.0)
    with pytest.raises(ValidationError):
        VerificationResult(plan_id="p1", passed="yes", exit_code=0, duration_seconds=1.0)
    with pytest.raises(ValidationError):
        VerificationResult(plan_id="p1", passed=True, exit_code=0, duration_seconds=-1.0)


def _improvement(**overrides) -> Improvement:
    kwargs = dict(  # noqa: C408
        id="i1",
        finding_id="f1",
        root_cause_id="rc1",
        title="fix it",
        description="d",
        scope=("src/x.py",),
        risks=("might break y",),
        verification_plan=_plan(),
        success_criteria="tests pass",
        regression_criteria="no new failures",
        rollback_guidance="git revert",
        estimated_effort="small",
    )
    kwargs.update(overrides)
    return Improvement(**kwargs)


def test_improvement_requires_verification_plan_instance():
    _improvement()
    with pytest.raises(ValidationError):
        _improvement(verification_plan="not a plan")


def test_improvement_coerces_list_scope_and_risks_to_tuples():
    # require_str_tuple accepts any string Sequence and normalizes it, so
    # a plain list of strings is valid input, not a validation error.
    improvement = _improvement(scope=["src/x.py"], risks=["r"])
    assert improvement.scope == ("src/x.py",)
    assert improvement.risks == ("r",)


def test_improvement_rejects_non_string_scope_entries():
    with pytest.raises(ValidationError):
        _improvement(scope=[1, 2])
    with pytest.raises(ValidationError):
        _improvement(risks=[1])


def test_improvement_requires_valid_status_enum():
    _improvement(status=ImprovementStatus.DISCOVERED)
    with pytest.raises(ValidationError):
        _improvement(status="discovered")


def _delta(**overrides) -> MetricDelta:
    kwargs = dict(  # noqa: C408
        metric="latency_ms",
        baseline_value=100.0,
        candidate_value=90.0,
        absolute_delta=-10.0,
        relative_delta=-0.1,
        meaningful=True,
        threshold=5.0,
    )
    kwargs.update(overrides)
    return MetricDelta(**kwargs)


def test_comparison_requires_valid_verdict_and_rationale():
    Comparison(
        id="c1",
        baseline_id="b1",
        candidate_id="cand1",
        verdict=ComparisonVerdict.ACCEPT,
        rationale="ok",
        deltas=(_delta(),),
    )
    with pytest.raises(ValidationError):
        Comparison(id="c1", baseline_id="b1", candidate_id="cand1", verdict="accept", rationale="ok", deltas=())
    with pytest.raises(ValidationError):
        Comparison(
            id="c1", baseline_id="b1", candidate_id="cand1", verdict=ComparisonVerdict.ACCEPT, rationale="", deltas=()
        )
    with pytest.raises(ValidationError):
        Comparison(
            id="c1",
            baseline_id="b1",
            candidate_id="cand1",
            verdict=ComparisonVerdict.ACCEPT,
            rationale="ok",
            deltas=[],  # not a tuple
        )


def test_improvement_outcome_requires_bool_accepted_and_nonblank_summary():
    ImprovementOutcome(id="o1", improvement_id="i1", comparison_id="c1", accepted=True, summary="worked")
    with pytest.raises(ValidationError):
        ImprovementOutcome(id="o1", improvement_id="i1", comparison_id="c1", accepted=1, summary="worked")
    with pytest.raises(ValidationError):
        ImprovementOutcome(id="o1", improvement_id="i1", comparison_id="c1", accepted=True, summary="")


def test_lesson_requires_nonblank_fields():
    Lesson(id="l1", improvement_id="i1", text="always test edge cases")
    with pytest.raises(ValidationError):
        Lesson(id="", improvement_id="i1", text="x")
    with pytest.raises(ValidationError):
        Lesson(id="l1", improvement_id="i1", text="")
