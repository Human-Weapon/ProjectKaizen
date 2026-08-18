from __future__ import annotations

from conftest import make_finding

from projectkaizen.models import Confidence, ImprovementViability, Severity, ViabilityStatus
from projectkaizen.prioritize import compute_priority, rank_findings


def test_higher_severity_ranks_higher():
    low = make_finding("low", severity=Severity.LOW, confidence=Confidence.MEDIUM)
    critical = make_finding("critical", severity=Severity.CRITICAL, confidence=Confidence.MEDIUM)
    ranked = rank_findings((low, critical))
    assert ranked[0].finding_id == "critical"


def test_viability_increases_priority():
    f = make_finding("f1")
    viable = ImprovementViability(status=ViabilityStatus.VIABLE, rationale="r")
    not_worth = ImprovementViability(status=ViabilityStatus.NOT_WORTH_IT, rationale="r")
    p_viable = compute_priority(f, viability=viable)
    p_not_worth = compute_priority(f, viability=not_worth)
    assert p_viable.total > p_not_worth.total


def test_missing_viability_uses_neutral_component():
    f = make_finding("f1")
    p = compute_priority(f, viability=None)
    assert 0.0 <= p.viability_component <= 1.0


def test_dependency_pressure_saturates_and_is_clamped():
    f = make_finding("f1")
    p_low = compute_priority(f, viability=None, dependency_pressure=0)
    p_high = compute_priority(f, viability=None, dependency_pressure=1000)
    assert p_high.dependency_pressure_component == 1.0
    assert p_high.total > p_low.total


def test_negative_dependency_pressure_clamped_to_zero():
    f = make_finding("f1")
    p = compute_priority(f, viability=None, dependency_pressure=-5)
    assert p.dependency_pressure_component == 0.0


def test_total_always_in_unit_interval():
    for severity in Severity:
        for confidence in Confidence:
            f = make_finding("f", severity=severity, confidence=confidence)
            p = compute_priority(f, viability=None)
            assert 0.0 <= p.total <= 1.0


def test_tie_break_by_severity_then_confidence_then_id():
    a = make_finding("a", severity=Severity.LOW, confidence=Confidence.LOW)
    b = make_finding("b", severity=Severity.LOW, confidence=Confidence.LOW)
    ranked = rank_findings((b, a))
    assert [r.finding_id for r in ranked] == ["a", "b"]


def test_rank_findings_is_deterministic_regardless_of_input_order():
    findings = tuple(make_finding(f"f{i}", severity=Severity.MEDIUM) for i in range(5))
    ranked1 = rank_findings(findings)
    ranked2 = rank_findings(tuple(reversed(findings)))
    assert [r.finding_id for r in ranked1] == [r.finding_id for r in ranked2]
