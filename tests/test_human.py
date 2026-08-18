from __future__ import annotations

from projectkaizen import human
from projectkaizen.attempt_policy import AttemptGuidance
from projectkaizen.blast_radius import BlastRadiusCategory
from projectkaizen.gates.fresh_evidence import EvidenceFreshness
from projectkaizen.gates.preservation import PreservationDecision
from projectkaizen.models import ComparisonVerdict, StoppingReason, ViabilityStatus
from projectkaizen.release.models import ChangeCategory, ReadinessOutcome, ReleaseFindingStatus
from projectkaizen.root_cause.base import RootCauseStrategyName


def test_every_viability_status_has_plain_text():
    for status in ViabilityStatus:
        text = human.plain_viability(status)
        assert text and status.value not in text


def test_every_stopping_reason_has_plain_text():
    for reason in StoppingReason:
        text = human.plain_stopping_reason(reason)
        assert text and reason.value not in text


def test_plain_stopping_reasons_joins_multiple():
    text = human.plain_stopping_reasons((StoppingReason.NO_RELEVANT_FINDINGS, StoppingReason.MARGINAL_ONLY))
    assert "; " in text


def test_plain_stopping_reasons_empty_tuple():
    assert human.plain_stopping_reasons(()) == ""


def test_every_verdict_has_plain_text():
    for verdict in ComparisonVerdict:
        text = human.plain_verdict(verdict)
        assert text


def test_every_readiness_outcome_has_plain_text():
    for outcome in ReadinessOutcome:
        text = human.plain_readiness_outcome(outcome)
        assert text


def test_no_blocker_found_never_reads_as_unqualified_safe():
    # "guaranteed"/"safe" may appear only inside an explicit negation
    # ("does not mean ... guaranteed safe") — never as a bare claim.
    text = human.plain_readiness_outcome(ReadinessOutcome.NO_BLOCKER_FOUND).lower()
    assert "does not mean" in text
    assert "guaranteed safe" in text


def test_every_finding_status_has_plain_text():
    for status in ReleaseFindingStatus:
        text = human.plain_finding_status(status)
        assert text


def test_every_change_category_has_plain_text():
    for category in ChangeCategory:
        text = human.plain_change_category(category)
        assert text


def test_every_evidence_freshness_has_plain_text_no_jargon():
    for freshness in EvidenceFreshness:
        text = human.plain_freshness(freshness)
        assert text
        assert "fresh" not in text.lower().split(".")[0] or freshness == EvidenceFreshness.FRESH


def test_stale_evidence_matches_spec_example_wording():
    text = human.plain_freshness(EvidenceFreshness.STALE)
    assert "earlier version" in text
    assert "run the verification again" in text.lower()


def test_every_blast_radius_category_has_plain_text():
    for category in BlastRadiusCategory:
        text = human.plain_blast_radius(category, consumer_count=14)
        assert text


def test_cross_module_blast_radius_matches_spec_example_wording():
    text = human.plain_blast_radius(BlastRadiusCategory.CROSS_MODULE, consumer_count=14)
    assert "14 other files" in text
    assert "broader regression testing" in text


def test_every_preservation_decision_has_plain_text():
    for decision in PreservationDecision:
        text = human.plain_preservation(decision)
        assert text


def test_intent_still_valid_matches_spec_example_wording():
    text = human.plain_preservation(PreservationDecision.INTENT_STILL_VALID)
    assert "don't remove this yet" in text.lower()
    assert "compatibility" not in text  # this specific example is generic, not compat-specific


def test_do_not_remove_mentions_compatibility_platform_or_performance():
    text = human.plain_preservation(PreservationDecision.DO_NOT_REMOVE)
    assert "compatibility" in text.lower()


def test_every_attempt_guidance_has_plain_text():
    for guidance in AttemptGuidance:
        text = human.plain_attempt_guidance(guidance)
        assert text


def test_architecture_review_required_matches_spec_example_wording():
    text = human.plain_attempt_guidance(AttemptGuidance.ARCHITECTURE_REVIEW_REQUIRED)
    assert text == (
        "Several fixes have failed under the same assumption. Re-check the design before trying another patch."
    )


def test_root_cause_label_is_methodology_agnostic():
    labels = {human.plain_root_cause_label(strategy) for strategy in RootCauseStrategyName}
    assert labels == {"Likely cause"}  # never leaks "Five Whys"/"Fishbone"/etc.
