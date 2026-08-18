from __future__ import annotations

import pytest

from projectkaizen.exceptions import ValidationError
from projectkaizen.method_selection import (
    ZERO_COST,
    AnalysisCost,
    AnalysisEngine,
    AnalysisMethodTier,
    DecisionSufficiency,
    MethodOption,
    MethodSelection,
    select_method,
    sufficiency_from_hard_gate_violations,
)


def test_sufficiency_from_hard_gate_violations_present():
    suff = sufficiency_from_hard_gate_violations(("required test failed",))
    assert suff.sufficient is True


def test_sufficiency_from_hard_gate_violations_absent():
    suff = sufficiency_from_hard_gate_violations(())
    assert suff.sufficient is False


def test_select_method_stops_when_sufficient_no_statistics_when_obvious():
    """spec: a failed required test, missing file, removed contract, etc.
    need no hypothesis test — the hard gate already decides it."""
    suff = sufficiency_from_hard_gate_violations(("public contract removed",))
    selection = select_method(
        sufficiency=suff,
        candidates=(MethodOption(AnalysisEngine.STATISTICAL_STRATEGY, AnalysisMethodTier.STATISTICAL),),
    )
    assert selection.should_analyze_further is False
    assert selection.chosen is None


def test_select_method_picks_cheapest_tier_when_insufficient():
    suff = DecisionSufficiency(sufficient=False, rationale="need more evidence")
    selection = select_method(
        sufficiency=suff,
        candidates=(
            MethodOption(AnalysisEngine.ROOT_CAUSE_STRATEGY, AnalysisMethodTier.CAUSAL_INVESTIGATION),
            MethodOption(AnalysisEngine.STATISTICAL_STRATEGY, AnalysisMethodTier.STATISTICAL),
            MethodOption(AnalysisEngine.GIT_HOTSPOTS, AnalysisMethodTier.DETERMINISTIC_RULE),
        ),
    )
    assert selection.chosen.engine == AnalysisEngine.GIT_HOTSPOTS  # cheapest tier


def test_select_method_prefers_lower_cost_within_same_tier():
    suff = DecisionSufficiency(sufficient=False, rationale="need more evidence")
    cheap = MethodOption(
        AnalysisEngine.STATISTICAL_STRATEGY, AnalysisMethodTier.STATISTICAL, AnalysisCost(compute_relative=0.1)
    )
    expensive = MethodOption(
        AnalysisEngine.RELEASE_READINESS, AnalysisMethodTier.STATISTICAL, AnalysisCost(compute_relative=10.0)
    )
    selection = select_method(sufficiency=suff, candidates=(expensive, cheap))
    assert selection.chosen.engine == AnalysisEngine.STATISTICAL_STRATEGY


def test_select_method_statistics_beats_causal_investigation_when_both_available():
    """Core requirement: statistical methods are not subordinate to
    continuous-improvement methodology — cheaper tier wins regardless of
    which "kind" of method it is."""
    suff = DecisionSufficiency(sufficient=False, rationale="need more evidence")
    selection = select_method(
        sufficiency=suff,
        candidates=(
            MethodOption(AnalysisEngine.ROOT_CAUSE_STRATEGY, AnalysisMethodTier.CAUSAL_INVESTIGATION),
            MethodOption(AnalysisEngine.STATISTICAL_STRATEGY, AnalysisMethodTier.STATISTICAL),
        ),
    )
    assert selection.chosen.engine == AnalysisEngine.STATISTICAL_STRATEGY


def test_select_method_no_candidates_still_needs_evidence_but_chooses_nothing():
    suff = DecisionSufficiency(sufficient=False, rationale="need more evidence", missing_for_decision=("x",))
    selection = select_method(sufficiency=suff, candidates=())
    assert selection.should_analyze_further is True
    assert selection.chosen is None


def test_analysis_cost_estimated_cost_weights_human_input_heavily():
    cheap = AnalysisCost(compute_relative=1.0)
    human = AnalysisCost(requires_human_input=True)
    assert human.estimated_cost > cheap.estimated_cost


def test_analysis_cost_rejects_negative_fields():
    with pytest.raises(ValidationError):
        AnalysisCost(compute_relative=-1.0)
    with pytest.raises(ValidationError):
        AnalysisCost(subprocess_calls=-1)


def test_zero_cost_is_actually_zero():
    assert ZERO_COST.estimated_cost == 0.0


def test_decision_sufficiency_requires_nonblank_rationale():
    with pytest.raises(ValidationError):
        DecisionSufficiency(sufficient=True, rationale="")


def test_method_selection_stop_state_cannot_carry_a_chosen_method():
    with pytest.raises(ValidationError):
        MethodSelection(
            should_analyze_further=False,
            chosen=MethodOption(AnalysisEngine.GIT_HOTSPOTS, AnalysisMethodTier.DETERMINISTIC_RULE),
            rationale="r",
        )


def test_method_selection_continue_state_without_chosen_is_valid():
    # legitimate: "keep looking" without a specific suggestion offered
    selection = MethodSelection(should_analyze_further=True, chosen=None, rationale="r")
    assert selection.chosen is None
