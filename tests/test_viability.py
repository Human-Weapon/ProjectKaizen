from __future__ import annotations

import pytest

from projectkaizen.models import Confidence, RootCauseStatus, ViabilityStatus
from projectkaizen.viability import ViabilityInputs, assess_viability, score_components


def test_missing_evidence_yields_insufficient_evidence():
    inputs = ViabilityInputs(RootCauseStatus.CONFIRMED, None, 0.1, 0.1, Confidence.HIGH)
    result = assess_viability(inputs)
    assert result.status == ViabilityStatus.INSUFFICIENT_EVIDENCE


@pytest.mark.parametrize("missing_field", ["expected_benefit", "effort_score", "risk_score"])
def test_each_missing_field_triggers_insufficient_evidence(missing_field):
    kwargs = {"expected_benefit": 0.5, "effort_score": 0.1, "risk_score": 0.1}
    kwargs[missing_field] = None
    inputs = ViabilityInputs(RootCauseStatus.CONFIRMED, confidence=Confidence.HIGH, **kwargs)
    assert assess_viability(inputs).status == ViabilityStatus.INSUFFICIENT_EVIDENCE


def test_possible_root_cause_and_irreversible_is_insufficient_evidence():
    inputs = ViabilityInputs(RootCauseStatus.POSSIBLE, 0.9, 0.1, 0.1, Confidence.HIGH, reversible=False)
    assert assess_viability(inputs).status == ViabilityStatus.INSUFFICIENT_EVIDENCE


def test_possible_root_cause_but_reversible_is_not_auto_blocked():
    inputs = ViabilityInputs(RootCauseStatus.POSSIBLE, 0.9, 0.1, 0.1, Confidence.HIGH, reversible=True)
    assert assess_viability(inputs).status != ViabilityStatus.INSUFFICIENT_EVIDENCE


def test_blocking_dependencies_yield_defer():
    inputs = ViabilityInputs(
        RootCauseStatus.CONFIRMED, 0.9, 0.1, 0.1, Confidence.HIGH, blocking_dependencies=("x", "y")
    )
    result = assess_viability(inputs)
    assert result.status == ViabilityStatus.DEFER
    assert "x" in result.rationale and "y" in result.rationale


def test_high_benefit_low_cost_is_viable():
    inputs = ViabilityInputs(RootCauseStatus.CONFIRMED, 0.9, 0.05, 0.05, Confidence.HIGH)
    assert assess_viability(inputs).status == ViabilityStatus.VIABLE


def test_low_benefit_is_not_worth_it():
    inputs = ViabilityInputs(RootCauseStatus.CONFIRMED, 0.05, 0.5, 0.5, Confidence.LOW)
    assert assess_viability(inputs).status == ViabilityStatus.NOT_WORTH_IT


def test_marginal_band_between_ceilings():
    # tuned to land strictly between 0.0 and MARGINAL_CEILING (0.15)
    inputs = ViabilityInputs(RootCauseStatus.CONFIRMED, 0.3, 0.1, 0.1, Confidence.HIGH)
    result = assess_viability(inputs)
    assert result.status == ViabilityStatus.MARGINAL


def test_irreversible_change_incurs_risk_multiplier():
    reversible = ViabilityInputs(RootCauseStatus.CONFIRMED, 0.5, 0.1, 0.3, Confidence.HIGH, reversible=True)
    irreversible = ViabilityInputs(RootCauseStatus.CONFIRMED, 0.5, 0.1, 0.3, Confidence.HIGH, reversible=False)
    assert score_components(irreversible) < score_components(reversible)


def test_score_components_is_deterministic():
    inputs = ViabilityInputs(RootCauseStatus.CONFIRMED, 0.5, 0.2, 0.1, Confidence.MEDIUM)
    assert score_components(inputs) == score_components(inputs)


def test_viability_result_exposes_all_inputs():
    inputs = ViabilityInputs(RootCauseStatus.CONFIRMED, 0.5, 0.2, 0.1, Confidence.MEDIUM, reversible=False)
    result = assess_viability(inputs)
    assert result.expected_benefit == 0.5
    assert result.effort_score == 0.2
    assert result.risk_score == 0.1
    assert result.confidence == Confidence.MEDIUM
    assert result.reversible is False
