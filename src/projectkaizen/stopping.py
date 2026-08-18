"""Diminishing returns, attempt budgets, and the StoppingPolicy.

KAIZEN_STABLE means "no currently worthwhile evidence-backed improvement
remains" — never "the software is perfect". A stopping decision always
carries at least one structured reason so a human can see exactly why
ProjectKaizen thinks nothing actionable is left.
"""

from __future__ import annotations

from collections.abc import Mapping

from .config import KaizenConfig
from .models import AttemptBudget, Finding, ImprovementViability, StoppingDecision, StoppingReason, ViabilityStatus

#: fixed, deterministic ordering used whenever multiple reasons apply
_REASON_PRIORITY: tuple[StoppingReason, ...] = (
    StoppingReason.NO_RELEVANT_FINDINGS,
    StoppingReason.TARGETS_ALREADY_MET,
    StoppingReason.ATTEMPT_BUDGET_EXHAUSTED,
    StoppingReason.DIMINISHING_RETURNS,
    StoppingReason.RISK_EXCEEDS_GAIN,
    StoppingReason.REMAINING_NOT_WORTH_IT,
    StoppingReason.MARGINAL_ONLY,
    StoppingReason.EXTERNAL_DEPENDENCY_REQUIRED,
    StoppingReason.INSUFFICIENT_EVIDENCE,
)


def _order_reasons(reasons: set[StoppingReason]) -> tuple[StoppingReason, ...]:
    return tuple(r for r in _REASON_PRIORITY if r in reasons)


def diminishing_returns(
    gains: tuple[float, ...],
    *,
    window: int,
    threshold_ratio: float,
) -> bool:
    """True when the last ``window`` gains are non-increasing and have
    shrunk to <= ``threshold_ratio`` of where the window started.

    Example: gains=(0.25, 0.08, 0.01, 0.001), window=3, threshold_ratio=0.3
    -> recent window is (0.08, 0.01, 0.001), monotonically decreasing, and
    0.001 / 0.08 = 0.0125 <= 0.3 -> True.
    """
    if window < 2 or len(gains) < window:
        return False
    recent = gains[-window:]
    if recent[0] <= 0:
        return False
    for i in range(len(recent) - 1):
        if recent[i + 1] > recent[i]:
            return False
    return (recent[-1] / recent[0]) <= threshold_ratio


def evaluate_stopping(
    *,
    remaining_findings: tuple[Finding, ...],
    viabilities: Mapping[str, ImprovementViability],
    attempt_budgets: Mapping[str, AttemptBudget] | None = None,
    gains_history: Mapping[str, tuple[float, ...]] | None = None,
    config: KaizenConfig,
    additional_reasons: tuple[StoppingReason, ...] = (),
) -> StoppingDecision:
    attempt_budgets = attempt_budgets or {}
    gains_history = gains_history or {}

    if not remaining_findings:
        return StoppingDecision(
            stable=True,
            reasons=(StoppingReason.NO_RELEVANT_FINDINGS,),
            rationale="no findings remain to evaluate",
        )

    reasons: set[StoppingReason] = set(additional_reasons)
    if reasons:
        # A caller-supplied reason (e.g. TARGETS_ALREADY_MET,
        # EXTERNAL_DEPENDENCY_REQUIRED, RISK_EXCEEDS_GAIN) reflects
        # information this module cannot derive on its own; trust it.
        return StoppingDecision(
            stable=True,
            reasons=_order_reasons(reasons),
            rationale="caller-supplied stopping evidence: " + ", ".join(r.value for r in _order_reasons(reasons)),
        )

    viable_ids = []
    marginal_ids = []
    not_worth_ids = []
    for finding in remaining_findings:
        status = viabilities.get(finding.id)
        if status is None:
            # No viability assessment yet: cannot claim stability.
            return StoppingDecision(
                stable=False,
                reasons=(),
                rationale=f"finding {finding.id} has not been through viability review yet",
            )
        if status.status == ViabilityStatus.VIABLE:
            viable_ids.append(finding.id)
        elif status.status == ViabilityStatus.MARGINAL:
            marginal_ids.append(finding.id)
        elif status.status == ViabilityStatus.NOT_WORTH_IT:
            not_worth_ids.append(finding.id)
        # DEFER / INSUFFICIENT_EVIDENCE findings fall through: they are
        # neither actionable nor a positive stopping signal on their own.

    if viable_ids:
        exhausted_ids = []
        diminishing_ids = []
        active_ids = []
        for fid in viable_ids:
            budget = attempt_budgets.get(fid)
            if budget is not None and budget.exhausted:
                exhausted_ids.append(fid)
                continue
            gains = gains_history.get(fid, ())
            if diminishing_returns(
                gains,
                window=config.diminishing_returns_window,
                threshold_ratio=config.diminishing_returns_threshold_ratio,
            ):
                diminishing_ids.append(fid)
                continue
            active_ids.append(fid)

        if active_ids:
            return StoppingDecision(
                stable=False,
                reasons=(),
                rationale=f"{len(active_ids)} viable improvement(s) still actionable: {', '.join(sorted(active_ids))}",
            )

        stop_reasons: set[StoppingReason] = set()
        if exhausted_ids:
            stop_reasons.add(StoppingReason.ATTEMPT_BUDGET_EXHAUSTED)
        if diminishing_ids:
            stop_reasons.add(StoppingReason.DIMINISHING_RETURNS)
        return StoppingDecision(
            stable=True,
            reasons=_order_reasons(stop_reasons),
            rationale=(
                f"all {len(viable_ids)} viable improvement(s) are exhausted "
                f"(budget: {sorted(exhausted_ids)}, diminishing returns: {sorted(diminishing_ids)})"
            ),
        )

    if marginal_ids and not not_worth_ids:
        return StoppingDecision(
            stable=True,
            reasons=(StoppingReason.MARGINAL_ONLY,),
            rationale=f"only marginal improvements remain: {', '.join(sorted(marginal_ids))}",
        )

    if not_worth_ids and len(not_worth_ids) == len(remaining_findings):
        return StoppingDecision(
            stable=True,
            reasons=(StoppingReason.REMAINING_NOT_WORTH_IT,),
            rationale=f"all remaining findings are NOT_WORTH_IT: {', '.join(sorted(not_worth_ids))}",
        )

    if not_worth_ids or marginal_ids:
        stop_reasons = set()
        if not_worth_ids:
            stop_reasons.add(StoppingReason.REMAINING_NOT_WORTH_IT)
        if marginal_ids:
            stop_reasons.add(StoppingReason.MARGINAL_ONLY)
        return StoppingDecision(
            stable=True,
            reasons=_order_reasons(stop_reasons),
            rationale="remaining findings are a mix of NOT_WORTH_IT and MARGINAL; nothing actionable",
        )

    return StoppingDecision(
        stable=True,
        reasons=(StoppingReason.INSUFFICIENT_EVIDENCE,),
        rationale="remaining findings are deferred or lack sufficient evidence to act on safely",
    )
