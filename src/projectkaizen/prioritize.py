"""Deterministic, explainable finding prioritization.

The formula is documented here, not buried in code: every weighted
component is exposed on :class:`PriorityResult` so "why is X ranked above Y"
is always answerable by reading the result, never by re-deriving the score.

    total = 0.40 * severity_component
          + 0.20 * confidence_component
          + 0.25 * viability_component
          + 0.15 * dependency_pressure_component

All components are clamped to ``[0.0, 1.0]`` before weighting, so ``total``
is always finite and in ``[0.0, 1.0]``. Missing information (no viability
assessment yet, no dependency data) degrades to a documented neutral value
rather than raising or producing NaN.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from .models import Confidence, Finding, ImprovementViability, ViabilityStatus, confidence_weight, severity_rank

SEVERITY_WEIGHT = 0.40
CONFIDENCE_WEIGHT = 0.20
VIABILITY_WEIGHT = 0.25
DEPENDENCY_PRESSURE_WEIGHT = 0.15

#: severity_rank 0 (CRITICAL) .. 4 (INFO) -> component 1.0 .. 0.0
_MAX_SEVERITY_RANK = 4

_VIABILITY_COMPONENT: Mapping[ViabilityStatus, float] = {
    ViabilityStatus.VIABLE: 1.0,
    ViabilityStatus.MARGINAL: 0.5,
    ViabilityStatus.DEFER: 0.2,
    ViabilityStatus.INSUFFICIENT_EVIDENCE: 0.1,
    ViabilityStatus.NOT_WORTH_IT: 0.0,
}
#: no viability assessment performed yet
_VIABILITY_COMPONENT_UNKNOWN = 0.3

#: dependency_pressure (number of other findings/improvements blocked on this
#: one) saturates at this count -> component 1.0
DEPENDENCY_PRESSURE_SATURATION = 5


@dataclass(frozen=True, slots=True)
class PriorityResult:
    finding_id: str
    total: float
    severity_component: float
    confidence_component: float
    viability_component: float
    dependency_pressure_component: float
    severity_rank: int
    confidence: Confidence


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def compute_priority(
    finding: Finding,
    *,
    viability: ImprovementViability | None,
    dependency_pressure: int = 0,
) -> PriorityResult:
    severity_component = _clamp01(1.0 - severity_rank(finding.severity) / _MAX_SEVERITY_RANK)
    confidence_component = _clamp01(confidence_weight(finding.confidence))
    viability_component = (
        _VIABILITY_COMPONENT[viability.status] if viability is not None else _VIABILITY_COMPONENT_UNKNOWN
    )
    dependency_pressure_component = _clamp01(max(0, dependency_pressure) / DEPENDENCY_PRESSURE_SATURATION)

    total = (
        SEVERITY_WEIGHT * severity_component
        + CONFIDENCE_WEIGHT * confidence_component
        + VIABILITY_WEIGHT * viability_component
        + DEPENDENCY_PRESSURE_WEIGHT * dependency_pressure_component
    )

    return PriorityResult(
        finding_id=finding.id,
        total=total,
        severity_component=severity_component,
        confidence_component=confidence_component,
        viability_component=viability_component,
        dependency_pressure_component=dependency_pressure_component,
        severity_rank=severity_rank(finding.severity),
        confidence=finding.confidence,
    )


def rank_findings(
    findings: tuple[Finding, ...],
    *,
    viabilities: Mapping[str, ImprovementViability] | None = None,
    dependency_pressure: Mapping[str, int] | None = None,
) -> tuple[PriorityResult, ...]:
    """Rank findings highest-priority first.

    Tie-breakers, in order: lower severity_rank (more severe), higher
    confidence_component, then ascending finding id — so ties never depend
    on input order or hashing.
    """
    viabilities = viabilities or {}
    dependency_pressure = dependency_pressure or {}
    results = [
        compute_priority(
            f,
            viability=viabilities.get(f.id),
            dependency_pressure=dependency_pressure.get(f.id, 0),
        )
        for f in findings
    ]
    results.sort(key=lambda r: (-r.total, r.severity_rank, -r.confidence_component, r.finding_id))
    return tuple(results)
