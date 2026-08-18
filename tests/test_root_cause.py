from __future__ import annotations

import pytest

from projectkaizen.exceptions import ValidationError
from projectkaizen.models import Confidence, RootCauseStatus
from projectkaizen.root_cause import (
    ALL_STRATEGIES,
    A3Result,
    FishboneCause,
    FishboneResult,
    FiveWhysResult,
    PdcaCycle,
    RootCauseStrategyName,
    TraceBackResult,
    TraceStep,
    WhyStep,
)


def test_all_strategies_has_five_entries():
    assert len(ALL_STRATEGIES) == 5
    assert set(ALL_STRATEGIES) == set(RootCauseStrategyName)


# --- Five Whys ---------------------------------------------------------


def test_five_whys_accepts_fewer_than_five_steps():
    result = FiveWhysResult(
        problem="p",
        steps=(WhyStep("why?", "because x", confidence=Confidence.HIGH),),
        termination_reason="reached actionable root cause",
        root_cause_status=RootCauseStatus.LIKELY,
    )
    assert len(result.steps) == 1


def test_five_whys_rejects_more_than_five_steps():
    with pytest.raises(ValidationError):
        FiveWhysResult(
            problem="p",
            steps=tuple(WhyStep("q", "a") for _ in range(6)),
            termination_reason="t",
            root_cause_status=RootCauseStatus.POSSIBLE,
        )


def test_five_whys_rejects_empty_steps():
    with pytest.raises(ValidationError):
        FiveWhysResult(problem="p", steps=(), termination_reason="t", root_cause_status=RootCauseStatus.POSSIBLE)


def test_five_whys_artifact_uses_last_step_confidence():
    result = FiveWhysResult(
        problem="p",
        steps=(
            WhyStep("q1", "a1", confidence=Confidence.LOW),
            WhyStep("q2", "a2", confidence=Confidence.HIGH),
        ),
        termination_reason="t",
        root_cause_status=RootCauseStatus.CONFIRMED,
    )
    artifact = result.to_artifact()
    assert artifact.confidence == Confidence.HIGH
    assert artifact.strategy == RootCauseStrategyName.FIVE_WHYS


# --- Fishbone ------------------------------------------------------------


def test_fishbone_requires_causes():
    with pytest.raises(ValidationError):
        FishboneResult(problem="p", causes=())


def test_fishbone_artifact_picks_strongest_confidence():
    result = FishboneResult(
        problem="p",
        causes=(
            FishboneCause("process", "weak", confidence=Confidence.LOW),
            FishboneCause("tools", "strong", confidence=Confidence.HIGH),
        ),
    )
    artifact = result.to_artifact()
    assert artifact.confidence == Confidence.HIGH


def test_fishbone_allows_project_specific_categories():
    result = FishboneResult(problem="p", causes=(FishboneCause("deployment_pipeline", "flaky step"),))
    assert result.causes[0].category == "deployment_pipeline"


# --- A3 --------------------------------------------------------------------


def test_a3_requires_all_core_fields():
    with pytest.raises(ValidationError):
        A3Result(
            problem="p",
            current_condition="",
            target_condition="t",
            root_cause="rc",
            countermeasure="cm",
            verification="v",
        )


def test_a3_to_artifact():
    result = A3Result(
        problem="p", current_condition="c", target_condition="t", root_cause="rc", countermeasure="cm", verification="v"
    )
    artifact = result.to_artifact()
    assert "rc" in artifact.summary


# --- PDCA --------------------------------------------------------------------


def test_pdca_requires_all_phases():
    with pytest.raises(ValidationError):
        PdcaCycle(plan="p", do="", check="c", act="a")


def test_pdca_records_outcome():
    cycle = PdcaCycle(plan="p", do="d", check="c", act="a", outcome="worked")
    artifact = cycle.to_artifact()
    assert "worked" in artifact.summary


# --- TraceBack ---------------------------------------------------------------


def test_traceback_requires_origin_with_no_caused_by():
    with pytest.raises(ValidationError):
        TraceBackResult(
            observed_bad_state="500s",
            steps=(TraceStep("500s", caused_by="timeout"), TraceStep("timeout", caused_by="still not origin")),
        )


def test_traceback_valid_chain():
    result = TraceBackResult(
        observed_bad_state="500s",
        steps=(TraceStep("500s", caused_by="db timeout"), TraceStep("db timeout")),
    )
    artifact = result.to_artifact()
    assert "db timeout" in artifact.summary


def test_traceback_rejects_empty_steps():
    with pytest.raises(ValidationError):
        TraceBackResult(observed_bad_state="x", steps=())
