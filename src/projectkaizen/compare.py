"""Baseline vs candidate comparison, hard gates, and honest rollback guidance.

Every improvement is judged against a real prior baseline, never against an
abstract idea of "perfect code" (spec section 16). A hard gate violation
(broken required functionality, broken critical tests, security regression,
data loss, broken promised compatibility, exceeded budget, platform
violation, removed required behavior) always rejects the candidate — no
average score can compensate for it (spec section 14).

ProjectKaizen never performs rollback itself. When a candidate is rejected,
this module only *describes* how a human/tool would roll back; it never
claims the rollback happened.
"""

from __future__ import annotations

from dataclasses import dataclass

from .config import KaizenConfig
from .models import (
    Baseline,
    Candidate,
    Comparison,
    ComparisonVerdict,
    MetricDelta,
    VerificationResult,
)
from .numbers import relative_delta

DEFAULT_ROLLBACK_GUIDANCE = (
    "ProjectKaizen did not modify the baseline. To discard the candidate, "
    "revert or discard the candidate's changes via your version control "
    "system (e.g. `git checkout -- <paths>` or `git reset`); the baseline "
    "remains the active, valid state."
)


@dataclass(frozen=True, slots=True)
class HardGateViolation:
    code: str
    detail: str

    def __str__(self) -> str:
        return f"{self.code}: {self.detail}"


def evaluate_verification_hard_gates(
    verification_results: tuple[VerificationResult, ...],
) -> tuple[HardGateViolation, ...]:
    """A failed verification command is always a hard gate violation.

    ProjectKaizen has no way to know a failing test was "unimportant" — the
    verification plan is what the improvement author declared as the
    success/regression bar, so any failure blocks acceptance.
    """
    violations = []
    for result in verification_results:
        if result.timed_out:
            violations.append(HardGateViolation(code="verification_timeout", detail=f"{result.plan_id} timed out"))
        elif not result.passed:
            violations.append(
                HardGateViolation(
                    code="verification_failed",
                    detail=f"{result.plan_id} exited {result.exit_code}",
                )
            )
    return tuple(violations)


def compute_deltas(
    baseline: Baseline,
    candidate: Candidate,
    *,
    config: KaizenConfig,
    higher_is_better: dict[str, bool] | None = None,
) -> tuple[MetricDelta, ...]:
    higher_is_better = higher_is_better or {}
    shared_metrics = sorted(set(baseline.metrics) & set(candidate.metrics))
    deltas = []
    for metric in shared_metrics:
        base_value = baseline.metrics[metric]
        cand_value = candidate.metrics[metric]
        absolute = cand_value - base_value
        threshold = config.meaningful_delta_for(metric, base_value)
        meaningful = abs(absolute) >= threshold if threshold > 0 else absolute != 0
        deltas.append(
            MetricDelta(
                metric=metric,
                baseline_value=base_value,
                candidate_value=cand_value,
                absolute_delta=absolute,
                relative_delta=relative_delta(base_value, cand_value),
                meaningful=meaningful,
                threshold=threshold,
            )
        )
    return tuple(deltas)


def _direction_improved(delta: MetricDelta, higher_is_better: dict[str, bool]) -> bool | None:
    if delta.absolute_delta == 0:
        return None
    wants_higher = higher_is_better.get(delta.metric, True)
    return (delta.absolute_delta > 0) == wants_higher


def compare(
    *,
    comparison_id: str,
    baseline: Baseline,
    candidate: Candidate,
    config: KaizenConfig,
    verification_results: tuple[VerificationResult, ...] = (),
    higher_is_better: dict[str, bool] | None = None,
    extra_hard_gate_violations: tuple[HardGateViolation, ...] = (),
) -> Comparison:
    higher_is_better = higher_is_better or {}
    hard_gates = evaluate_verification_hard_gates(verification_results) + tuple(extra_hard_gate_violations)
    deltas = compute_deltas(baseline, candidate, config=config, higher_is_better=higher_is_better)

    if hard_gates:
        return Comparison(
            id=comparison_id,
            baseline_id=baseline.id,
            candidate_id=candidate.id,
            verdict=ComparisonVerdict.REJECT,
            rationale=(
                f"{len(hard_gates)} hard gate violation(s); no score can compensate: "
                + "; ".join(str(v) for v in hard_gates)
            ),
            deltas=deltas,
            hard_gate_violations=tuple(str(v) for v in hard_gates),
            rollback_guidance=DEFAULT_ROLLBACK_GUIDANCE,
        )

    any_timed_out = any(r.timed_out for r in verification_results)
    meaningful = [d for d in deltas if d.meaningful]
    regressed = [d for d in meaningful if _direction_improved(d, higher_is_better) is False]
    improved = [d for d in meaningful if _direction_improved(d, higher_is_better) is True]

    if regressed:
        metrics = ", ".join(d.metric for d in regressed)
        return Comparison(
            id=comparison_id,
            baseline_id=baseline.id,
            candidate_id=candidate.id,
            verdict=ComparisonVerdict.REJECT,
            rationale=f"meaningful regression on: {metrics}; baseline remains the valid state",
            deltas=deltas,
            rollback_guidance=DEFAULT_ROLLBACK_GUIDANCE,
        )

    if not meaningful:
        reason = (
            "verification timed out; insufficient signal"
            if any_timed_out
            else "no metric crossed its minimum meaningful delta threshold"
        )
        return Comparison(
            id=comparison_id,
            baseline_id=baseline.id,
            candidate_id=candidate.id,
            verdict=ComparisonVerdict.DEFER if any_timed_out else ComparisonVerdict.INCONCLUSIVE,
            rationale=reason,
            deltas=deltas,
            rollback_guidance=DEFAULT_ROLLBACK_GUIDANCE,
        )

    metrics = ", ".join(d.metric for d in improved)
    return Comparison(
        id=comparison_id,
        baseline_id=baseline.id,
        candidate_id=candidate.id,
        verdict=ComparisonVerdict.ACCEPT,
        rationale=f"meaningful improvement on: {metrics}; no regressions or hard gate violations",
        deltas=deltas,
    )
