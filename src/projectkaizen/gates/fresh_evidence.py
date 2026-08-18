"""The Fresh Evidence Gate: an improvement cannot be ACCEPTED on stale proof.

Verification evidence is only useful if it is provably about the exact
candidate being judged right now — not "a candidate that used to look like
this." Evidence binds to a candidate through a stable identity (a git
commit, a content fingerprint, an artifact digest, or an explicit manual
attestation); a mismatch, absence, or unverifiable binding all block
ACCEPT, each for an honestly distinguishable reason.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from ..exceptions import ValidationError
from ..numbers import require_nonblank_str


class IdentityKind(str, Enum):
    GIT_COMMIT = "git_commit"
    TREE_FINGERPRINT = "tree_fingerprint"
    ARTIFACT_DIGEST = "artifact_digest"
    MANUAL = "manual"


class EvidenceFreshness(str, Enum):
    #: bound to the exact candidate identity being evaluated
    FRESH = "fresh"
    #: bound to a *different*, verifiable candidate identity
    STALE = "stale"
    #: carries no candidate identity at all (not even a manual attestation)
    UNBOUND = "unbound"
    #: carries a human attestation but no structurally verifiable identity
    INSUFFICIENT = "insufficient"


@dataclass(frozen=True, slots=True)
class CandidateIdentity:
    kind: IdentityKind
    value: str

    def __post_init__(self) -> None:
        if not isinstance(self.kind, IdentityKind):
            raise ValidationError("candidate_identity.kind must be an IdentityKind")
        object.__setattr__(self, "value", require_nonblank_str(self.value, name="candidate_identity.value"))

    def to_jsonable(self) -> dict[str, Any]:
        return {"kind": self.kind.value, "value": self.value}

    @classmethod
    def from_mapping(cls, raw: dict[str, Any]) -> CandidateIdentity:
        try:
            kind = IdentityKind(raw["kind"])
        except (KeyError, ValueError) as exc:
            raise ValidationError(f"invalid candidate identity kind: {raw.get('kind')!r}") from exc
        return cls(kind=kind, value=raw["value"])

    def matches(self, other: CandidateIdentity) -> bool:
        return self.kind == other.kind and self.value == other.value


@dataclass(frozen=True, slots=True)
class VerificationEvidence:
    id: str
    description: str
    candidate_identity: CandidateIdentity | None = None
    manual_attestation: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", require_nonblank_str(self.id, name="verification_evidence.id"))
        object.__setattr__(
            self, "description", require_nonblank_str(self.description, name="verification_evidence.description")
        )
        if self.candidate_identity is not None and not isinstance(self.candidate_identity, CandidateIdentity):
            raise ValidationError("verification_evidence.candidate_identity must be a CandidateIdentity or None")
        if self.manual_attestation is not None:
            object.__setattr__(
                self,
                "manual_attestation",
                require_nonblank_str(self.manual_attestation, name="verification_evidence.manual_attestation"),
            )

    def to_jsonable(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "description": self.description,
            "candidate_identity": self.candidate_identity.to_jsonable() if self.candidate_identity else None,
            "manual_attestation": self.manual_attestation,
        }

    @classmethod
    def from_mapping(cls, raw: dict[str, Any]) -> VerificationEvidence:
        identity_raw = raw.get("candidate_identity")
        return cls(
            id=raw["id"],
            description=raw["description"],
            candidate_identity=CandidateIdentity.from_mapping(identity_raw) if identity_raw else None,
            manual_attestation=raw.get("manual_attestation"),
        )


def evaluate_freshness(*, candidate_identity: CandidateIdentity, evidence: VerificationEvidence) -> EvidenceFreshness:
    if evidence.candidate_identity is None:
        return EvidenceFreshness.INSUFFICIENT if evidence.manual_attestation else EvidenceFreshness.UNBOUND
    if evidence.candidate_identity.matches(candidate_identity):
        return EvidenceFreshness.FRESH
    return EvidenceFreshness.STALE


@dataclass(frozen=True, slots=True)
class FreshEvidenceDecision:
    can_accept: bool
    freshness: EvidenceFreshness
    rationale: str


_RATIONALE = {
    EvidenceFreshness.FRESH: "evidence identity matches the candidate being evaluated",
    EvidenceFreshness.STALE: "evidence is bound to a different candidate identity; re-verify against this candidate",
    EvidenceFreshness.UNBOUND: (
        "evidence carries no candidate identity at all; cannot confirm it is about this candidate"
    ),
    EvidenceFreshness.INSUFFICIENT: (
        "evidence carries only a manual attestation with no structurally verifiable identity; "
        "honest, but not sufficient to ACCEPT on its own"
    ),
}


def gate(*, candidate_identity: CandidateIdentity, evidence: VerificationEvidence) -> FreshEvidenceDecision:
    freshness = evaluate_freshness(candidate_identity=candidate_identity, evidence=evidence)
    return FreshEvidenceDecision(
        can_accept=freshness == EvidenceFreshness.FRESH, freshness=freshness, rationale=_RATIONALE[freshness]
    )


def gate_all(
    *, candidate_identity: CandidateIdentity, evidence: tuple[VerificationEvidence, ...]
) -> FreshEvidenceDecision:
    """A candidate can only ACCEPT if every piece of supporting evidence is FRESH.

    The worst status among the set is reported (UNBOUND is treated as worse
    than INSUFFICIENT, which is worse than STALE) so a caller sees the most
    serious problem first.
    """
    if not evidence:
        return FreshEvidenceDecision(
            can_accept=False, freshness=EvidenceFreshness.UNBOUND, rationale="no evidence was supplied at all"
        )
    severity = {
        EvidenceFreshness.UNBOUND: 0,
        EvidenceFreshness.INSUFFICIENT: 1,
        EvidenceFreshness.STALE: 2,
        EvidenceFreshness.FRESH: 3,
    }
    decisions = [gate(candidate_identity=candidate_identity, evidence=e) for e in evidence]
    worst = min(decisions, key=lambda d: severity[d.freshness])
    if worst.freshness == EvidenceFreshness.FRESH:
        return FreshEvidenceDecision(
            can_accept=True, freshness=EvidenceFreshness.FRESH, rationale=f"all {len(evidence)} evidence item(s) fresh"
        )
    return FreshEvidenceDecision(can_accept=False, freshness=worst.freshness, rationale=worst.rationale)
