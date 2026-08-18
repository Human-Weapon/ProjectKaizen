"""ImprovementViability gate.

The existence of a possible improvement does not imply that implementing it
is worthwhile. This module decides whether a candidate improvement should
move toward implementation, and — critically — whether the evidence backing
it is even strong enough to decide safely.

The formula is intentionally simple and fully exposed: every component that
fed the decision is returned on the result so a caller can answer
"why is X ranked/gated the way it is" without re-deriving anything.
"""

from __future__ import annotations

from dataclasses import dataclass

from .models import Confidence, ImprovementViability, RootCauseStatus, ViabilityStatus, confidence_weight

#: score <= NOT_WORTH_IT_CEILING -> NOT_WORTH_IT
NOT_WORTH_IT_CEILING = 0.0
#: NOT_WORTH_IT_CEILING < score < MARGINAL_CEILING -> MARGINAL
MARGINAL_CEILING = 0.15
#: multiplier applied to risk when the change is not reversible
IRREVERSIBLE_RISK_MULTIPLIER = 1.5


@dataclass(frozen=True, slots=True)
class ViabilityInputs:
    """Everything the viability formula needs. Missing evidence is explicit."""

    root_cause_status: RootCauseStatus
    expected_benefit: float | None
    effort_score: float | None
    risk_score: float | None
    confidence: Confidence
    reversible: bool = True
    blocking_dependencies: tuple[str, ...] = ()
    verification_cost: str = "low"


def score_components(inputs: ViabilityInputs) -> float:
    """score = benefit * confidence_weight - effort - risk * irreversibility_multiplier.

    All three of benefit/effort/risk are expected on a comparable [0, 1]-ish
    scale by convention; callers that use other scales get a differently
    calibrated but still deterministic and monotonic score.
    """
    benefit = inputs.expected_benefit or 0.0
    effort = inputs.effort_score or 0.0
    risk = inputs.risk_score or 0.0
    risk_multiplier = IRREVERSIBLE_RISK_MULTIPLIER if not inputs.reversible else 1.0
    return benefit * confidence_weight(inputs.confidence) - effort - risk * risk_multiplier


def assess_viability(inputs: ViabilityInputs) -> ImprovementViability:
    if inputs.expected_benefit is None or inputs.effort_score is None or inputs.risk_score is None:
        return ImprovementViability(
            status=ViabilityStatus.INSUFFICIENT_EVIDENCE,
            rationale="expected_benefit, effort_score, and risk_score are all required to assess viability",
            expected_benefit=inputs.expected_benefit,
            effort_score=inputs.effort_score,
            risk_score=inputs.risk_score,
            confidence=inputs.confidence,
            reversible=inputs.reversible,
            verification_cost=inputs.verification_cost,
            blocking_dependencies=inputs.blocking_dependencies,
        )

    if inputs.root_cause_status == RootCauseStatus.POSSIBLE and not inputs.reversible:
        return ImprovementViability(
            status=ViabilityStatus.INSUFFICIENT_EVIDENCE,
            rationale=(
                "root cause is only POSSIBLE (unconfirmed) and the change is not reversible; "
                "intervening now would be a dangerous guess"
            ),
            expected_benefit=inputs.expected_benefit,
            effort_score=inputs.effort_score,
            risk_score=inputs.risk_score,
            confidence=inputs.confidence,
            reversible=inputs.reversible,
            verification_cost=inputs.verification_cost,
            blocking_dependencies=inputs.blocking_dependencies,
        )

    if inputs.blocking_dependencies:
        return ImprovementViability(
            status=ViabilityStatus.DEFER,
            rationale=f"blocked on unresolved dependencies: {', '.join(inputs.blocking_dependencies)}",
            expected_benefit=inputs.expected_benefit,
            effort_score=inputs.effort_score,
            risk_score=inputs.risk_score,
            confidence=inputs.confidence,
            reversible=inputs.reversible,
            verification_cost=inputs.verification_cost,
            blocking_dependencies=inputs.blocking_dependencies,
        )

    score = score_components(inputs)
    if score <= NOT_WORTH_IT_CEILING:
        status = ViabilityStatus.NOT_WORTH_IT
        rationale = f"score={score:.3f} <= {NOT_WORTH_IT_CEILING}: expected cost/risk outweighs expected benefit"
    elif score < MARGINAL_CEILING:
        status = ViabilityStatus.MARGINAL
        rationale = f"score={score:.3f} is positive but below the marginal ceiling {MARGINAL_CEILING}"
    else:
        status = ViabilityStatus.VIABLE
        rationale = f"score={score:.3f} clears the marginal ceiling {MARGINAL_CEILING}"

    return ImprovementViability(
        status=status,
        rationale=rationale,
        expected_benefit=inputs.expected_benefit,
        effort_score=inputs.effort_score,
        risk_score=inputs.risk_score,
        confidence=inputs.confidence,
        reversible=inputs.reversible,
        verification_cost=inputs.verification_cost,
        blocking_dependencies=inputs.blocking_dependencies,
    )
