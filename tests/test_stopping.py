from __future__ import annotations

from conftest import make_finding

from projectkaizen.config import KaizenConfig
from projectkaizen.models import AttemptBudget, ImprovementViability, StoppingReason, ViabilityStatus
from projectkaizen.stopping import diminishing_returns, evaluate_stopping


def test_no_findings_is_stable():
    d = evaluate_stopping(remaining_findings=(), viabilities={}, config=KaizenConfig())
    assert d.stable is True
    assert d.reasons == (StoppingReason.NO_RELEVANT_FINDINGS,)


def test_finding_without_viability_review_is_not_stable():
    f = make_finding("f1")
    d = evaluate_stopping(remaining_findings=(f,), viabilities={}, config=KaizenConfig())
    assert d.stable is False


def test_viable_finding_with_budget_still_available_is_not_stable():
    f = make_finding("f1")
    viab = {"f1": ImprovementViability(status=ViabilityStatus.VIABLE, rationale="ok")}
    d = evaluate_stopping(remaining_findings=(f,), viabilities=viab, config=KaizenConfig())
    assert d.stable is False


def test_viable_finding_with_exhausted_budget_is_stable():
    f = make_finding("f1")
    viab = {"f1": ImprovementViability(status=ViabilityStatus.VIABLE, rationale="ok")}
    budgets = {"f1": AttemptBudget(improvement_id="f1", max_attempts=2, attempts_used=2)}
    d = evaluate_stopping(remaining_findings=(f,), viabilities=viab, attempt_budgets=budgets, config=KaizenConfig())
    assert d.stable is True
    assert StoppingReason.ATTEMPT_BUDGET_EXHAUSTED in d.reasons


def test_viable_finding_with_diminishing_returns_is_stable():
    f = make_finding("f1")
    viab = {"f1": ImprovementViability(status=ViabilityStatus.VIABLE, rationale="ok")}
    gains = {"f1": (0.25, 0.08, 0.01)}
    cfg = KaizenConfig.from_mapping({"diminishing_returns_window": 3, "diminishing_returns_threshold_ratio": 0.3})
    d = evaluate_stopping(remaining_findings=(f,), viabilities=viab, gains_history=gains, config=cfg)
    assert d.stable is True
    assert StoppingReason.DIMINISHING_RETURNS in d.reasons


def test_all_not_worth_it_is_stable():
    f = make_finding("f1")
    viab = {"f1": ImprovementViability(status=ViabilityStatus.NOT_WORTH_IT, rationale="no")}
    d = evaluate_stopping(remaining_findings=(f,), viabilities=viab, config=KaizenConfig())
    assert d.stable is True
    assert d.reasons == (StoppingReason.REMAINING_NOT_WORTH_IT,)


def test_all_marginal_is_stable():
    f = make_finding("f1")
    viab = {"f1": ImprovementViability(status=ViabilityStatus.MARGINAL, rationale="meh")}
    d = evaluate_stopping(remaining_findings=(f,), viabilities=viab, config=KaizenConfig())
    assert d.stable is True
    assert d.reasons == (StoppingReason.MARGINAL_ONLY,)


def test_mixed_marginal_and_not_worth_it_is_stable_with_both_reasons():
    f1 = make_finding("f1")
    f2 = make_finding("f2")
    viab = {
        "f1": ImprovementViability(status=ViabilityStatus.MARGINAL, rationale="meh"),
        "f2": ImprovementViability(status=ViabilityStatus.NOT_WORTH_IT, rationale="no"),
    }
    d = evaluate_stopping(remaining_findings=(f1, f2), viabilities=viab, config=KaizenConfig())
    assert d.stable is True
    assert StoppingReason.MARGINAL_ONLY in d.reasons
    assert StoppingReason.REMAINING_NOT_WORTH_IT in d.reasons


def test_all_deferred_or_insufficient_is_insufficient_evidence():
    f = make_finding("f1")
    viab = {"f1": ImprovementViability(status=ViabilityStatus.DEFER, rationale="blocked")}
    d = evaluate_stopping(remaining_findings=(f,), viabilities=viab, config=KaizenConfig())
    assert d.stable is True
    assert d.reasons == (StoppingReason.INSUFFICIENT_EVIDENCE,)


def test_additional_reasons_short_circuit_to_stable():
    f = make_finding("f1")
    d = evaluate_stopping(
        remaining_findings=(f,),
        viabilities={},
        config=KaizenConfig(),
        additional_reasons=(StoppingReason.TARGETS_ALREADY_MET,),
    )
    assert d.stable is True
    assert d.reasons == (StoppingReason.TARGETS_ALREADY_MET,)


def test_reason_ordering_is_deterministic_regardless_of_insertion():
    f1 = make_finding("f1")
    f2 = make_finding("f2")
    viab = {
        "f1": ImprovementViability(status=ViabilityStatus.NOT_WORTH_IT, rationale="no"),
        "f2": ImprovementViability(status=ViabilityStatus.MARGINAL, rationale="meh"),
    }
    d1 = evaluate_stopping(remaining_findings=(f1, f2), viabilities=viab, config=KaizenConfig())
    d2 = evaluate_stopping(remaining_findings=(f2, f1), viabilities=viab, config=KaizenConfig())
    assert d1.reasons == d2.reasons


def test_diminishing_returns_requires_full_window():
    assert diminishing_returns((0.25, 0.08), window=3, threshold_ratio=0.3) is False


def test_diminishing_returns_requires_monotonic_decrease():
    assert diminishing_returns((0.1, 0.2, 0.01), window=3, threshold_ratio=0.3) is False


def test_diminishing_returns_zero_start_is_false():
    assert diminishing_returns((0.0, 0.0, 0.0), window=3, threshold_ratio=0.3) is False


def test_diminishing_returns_classic_example():
    assert diminishing_returns((0.25, 0.08, 0.01, 0.001), window=3, threshold_ratio=0.3) is True


def test_diminishing_returns_window_too_small_returns_false():
    assert diminishing_returns((0.25, 0.08, 0.01), window=1, threshold_ratio=0.3) is False
