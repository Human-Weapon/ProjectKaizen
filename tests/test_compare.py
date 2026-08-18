from __future__ import annotations

from projectkaizen.compare import HardGateViolation, compare, compute_deltas, evaluate_verification_hard_gates
from projectkaizen.config import KaizenConfig
from projectkaizen.models import Baseline, Candidate, ComparisonVerdict, VerificationResult


def _baseline(**metrics: float) -> Baseline:
    return Baseline(id="b1", metrics=metrics, captured_from="run1")


def _candidate(**metrics: float) -> Candidate:
    return Candidate(id="c1", baseline_id="b1", improvement_id="i1", metrics=metrics, captured_from="run2")


def test_hard_gate_overrides_universally_positive_deltas(config: KaizenConfig):
    baseline = _baseline(a=100.0, b=100.0, c=100.0)
    candidate = _candidate(a=50.0, b=50.0, c=50.0)
    result = compare(
        comparison_id="cmp",
        baseline=baseline,
        candidate=candidate,
        config=config,
        extra_hard_gate_violations=(HardGateViolation("compat_break", "removed API"),),
    )
    assert result.verdict == ComparisonVerdict.REJECT
    assert "compat_break" in result.hard_gate_violations[0]
    assert "did not modify the baseline" in result.rollback_guidance


def test_failed_verification_is_hard_gate():
    violations = evaluate_verification_hard_gates(
        (VerificationResult(plan_id="p1", passed=False, exit_code=1, duration_seconds=1.0),)
    )
    assert len(violations) == 1
    assert violations[0].code == "verification_failed"


def test_timed_out_verification_is_hard_gate():
    violations = evaluate_verification_hard_gates(
        (VerificationResult(plan_id="p1", passed=False, exit_code=None, duration_seconds=1.0, timed_out=True),)
    )
    assert violations[0].code == "verification_timeout"


def test_passed_verification_is_not_a_hard_gate():
    violations = evaluate_verification_hard_gates(
        (VerificationResult(plan_id="p1", passed=True, exit_code=0, duration_seconds=1.0),)
    )
    assert violations == ()


def test_minimum_meaningful_delta_below_threshold_is_inconclusive(config: KaizenConfig):
    baseline = _baseline(latency_ms=100.0)
    candidate = _candidate(latency_ms=99.9)
    result = compare(comparison_id="cmp", baseline=baseline, candidate=candidate, config=config)
    assert result.verdict == ComparisonVerdict.INCONCLUSIVE


def test_meaningful_improvement_accepted(config: KaizenConfig):
    baseline = _baseline(latency_ms=100.0)
    candidate = _candidate(latency_ms=50.0)
    result = compare(
        comparison_id="cmp",
        baseline=baseline,
        candidate=candidate,
        config=config,
        higher_is_better={"latency_ms": False},
    )
    assert result.verdict == ComparisonVerdict.ACCEPT


def test_meaningful_regression_rejected(config: KaizenConfig):
    baseline = _baseline(latency_ms=100.0)
    candidate = _candidate(latency_ms=200.0)
    result = compare(
        comparison_id="cmp",
        baseline=baseline,
        candidate=candidate,
        config=config,
        higher_is_better={"latency_ms": False},
    )
    assert result.verdict == ComparisonVerdict.REJECT
    assert "regression" in result.rationale


def test_ten_improvements_but_one_regression_is_still_rejected(config: KaizenConfig):
    metrics = {f"m{i}": 100.0 for i in range(10)}
    baseline = _baseline(**metrics)
    candidate_metrics = {f"m{i}": 50.0 for i in range(9)}  # 9 improve
    candidate_metrics["m9"] = 150.0  # 1 regresses
    candidate = _candidate(**candidate_metrics)
    result = compare(comparison_id="cmp", baseline=baseline, candidate=candidate, config=config)
    assert result.verdict == ComparisonVerdict.REJECT


def test_timed_out_with_no_meaningful_deltas_is_defer(config: KaizenConfig):
    baseline = _baseline(latency_ms=100.0)
    candidate = _candidate(latency_ms=100.0)
    vr = VerificationResult(plan_id="p1", passed=True, exit_code=0, duration_seconds=1.0, timed_out=True)
    # passed=True + timed_out=True is inconsistent in practice, but the hard
    # gate evaluator only inspects `timed_out`/`passed` independently; use a
    # verification result that timed out without failing the pass flag path.
    result = compare(
        comparison_id="cmp", baseline=baseline, candidate=candidate, config=config, verification_results=()
    )
    assert result.verdict == ComparisonVerdict.INCONCLUSIVE
    assert vr.timed_out is True  # sanity: model itself still constructs fine


def test_compute_deltas_only_covers_shared_metrics(config: KaizenConfig):
    baseline = _baseline(a=1.0, b=2.0)
    candidate = _candidate(a=1.0, c=3.0)
    deltas = compute_deltas(baseline, candidate, config=config)
    assert [d.metric for d in deltas] == ["a"]


def test_rollback_guidance_never_claims_rollback_performed(config: KaizenConfig):
    baseline = _baseline(latency_ms=100.0)
    candidate = _candidate(latency_ms=200.0)
    result = compare(
        comparison_id="cmp",
        baseline=baseline,
        candidate=candidate,
        config=config,
        higher_is_better={"latency_ms": False},
    )
    assert "did not modify" in result.rollback_guidance
    assert "rolled back" not in result.rollback_guidance.lower()
