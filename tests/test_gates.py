from __future__ import annotations

import pytest

from projectkaizen.exceptions import ValidationError
from projectkaizen.gates.fresh_evidence import (
    CandidateIdentity,
    EvidenceFreshness,
    IdentityKind,
    VerificationEvidence,
    gate,
    gate_all,
)
from projectkaizen.gates.preservation import PreservationDecision, PreservationEvidence, evaluate_preservation


def _identity(value: str = "abc123") -> CandidateIdentity:
    return CandidateIdentity(IdentityKind.GIT_COMMIT, value)


def test_fresh_evidence_stale_when_bound_to_different_candidate():
    old = _identity("old")
    new = _identity("new")
    evidence = VerificationEvidence(id="e1", description="pytest", candidate_identity=old)
    result = gate(candidate_identity=new, evidence=evidence)
    assert result.freshness == EvidenceFreshness.STALE
    assert result.can_accept is False


def test_fresh_evidence_fresh_when_identity_matches():
    identity = _identity()
    evidence = VerificationEvidence(id="e1", description="pytest", candidate_identity=identity)
    result = gate(candidate_identity=identity, evidence=evidence)
    assert result.freshness == EvidenceFreshness.FRESH
    assert result.can_accept is True


def test_fresh_evidence_unbound_with_no_identity_or_attestation():
    evidence = VerificationEvidence(id="e1", description="someone said so")
    result = gate(candidate_identity=_identity(), evidence=evidence)
    assert result.freshness == EvidenceFreshness.UNBOUND
    assert result.can_accept is False


def test_fresh_evidence_manual_attestation_is_insufficient_not_fresh():
    evidence = VerificationEvidence(id="e1", description="manual check", manual_attestation="ran it myself")
    result = gate(candidate_identity=_identity(), evidence=evidence)
    assert result.freshness == EvidenceFreshness.INSUFFICIENT
    assert result.can_accept is False


def test_fresh_evidence_serialization_roundtrip_retains_identity():
    identity = _identity()
    evidence = VerificationEvidence(id="e1", description="pytest", candidate_identity=identity)
    restored = VerificationEvidence.from_mapping(evidence.to_jsonable())
    assert restored == evidence
    result = gate(candidate_identity=identity, evidence=restored)
    assert result.freshness == EvidenceFreshness.FRESH


def test_fresh_evidence_kind_mismatch_is_stale_even_with_same_value():
    a = CandidateIdentity(IdentityKind.GIT_COMMIT, "x")
    b = CandidateIdentity(IdentityKind.ARTIFACT_DIGEST, "x")
    evidence = VerificationEvidence(id="e1", description="d", candidate_identity=a)
    result = gate(candidate_identity=b, evidence=evidence)
    assert result.freshness == EvidenceFreshness.STALE


def test_gate_all_empty_evidence_is_unbound():
    result = gate_all(candidate_identity=_identity(), evidence=())
    assert result.can_accept is False
    assert result.freshness == EvidenceFreshness.UNBOUND


def test_gate_all_requires_every_item_fresh():
    identity = _identity()
    fresh = VerificationEvidence(id="e1", description="d", candidate_identity=identity)
    stale = VerificationEvidence(id="e2", description="d", candidate_identity=_identity("other"))
    result = gate_all(candidate_identity=identity, evidence=(fresh, stale))
    assert result.can_accept is False


def test_gate_all_accepts_when_all_fresh():
    identity = _identity()
    a = VerificationEvidence(id="e1", description="d", candidate_identity=identity)
    b = VerificationEvidence(id="e2", description="d2", candidate_identity=identity)
    result = gate_all(candidate_identity=identity, evidence=(a, b))
    assert result.can_accept is True


def test_candidate_identity_rejects_blank_value():
    with pytest.raises(ValidationError):
        CandidateIdentity(IdentityKind.GIT_COMMIT, "")


# --- Preservation gate -------------------------------------------------------


def _full_evidence(**overrides) -> PreservationEvidence:
    kwargs = {
        "target_description": "thing()",
        "caller_count": 1,
        "has_tests": True,
        "referenced_by_adr": False,
        "referenced_by_project_guidance": False,
        "recent_git_activity": False,
        "compatibility_constraint": False,
        "platform_specific": False,
        "performance_constraint": False,
    }
    kwargs.update(overrides)
    return PreservationEvidence(**kwargs)


def test_preservation_insufficient_context_when_fields_unknown():
    result = evaluate_preservation(PreservationEvidence(target_description="old_helper()"))
    assert result.decision == PreservationDecision.REQUIRES_MORE_CONTEXT


def test_preservation_hard_constraint_blocks_removal():
    result = evaluate_preservation(_full_evidence(compatibility_constraint=True))
    assert result.decision == PreservationDecision.DO_NOT_REMOVE


def test_preservation_adr_reference_is_intent_still_valid():
    result = evaluate_preservation(_full_evidence(referenced_by_adr=True))
    assert result.decision == PreservationDecision.INTENT_STILL_VALID


def test_preservation_safe_removal_when_zero_callers_and_no_signals():
    result = evaluate_preservation(_full_evidence(caller_count=0))
    assert result.decision == PreservationDecision.SAFE_TO_CHANGE


def test_preservation_hard_constraint_wins_even_with_unknown_fields():
    evidence = PreservationEvidence(target_description="x()", compatibility_constraint=True)
    result = evaluate_preservation(evidence)
    assert result.decision == PreservationDecision.DO_NOT_REMOVE


def test_preservation_callers_present_requires_more_context():
    result = evaluate_preservation(_full_evidence(caller_count=5))
    assert result.decision == PreservationDecision.REQUIRES_MORE_CONTEXT


def test_preservation_rejects_negative_caller_count():
    with pytest.raises(ValidationError):
        _full_evidence(caller_count=-1)
