"""TraceBack: trace an observed bad state backward through evidence.

Named after the general "walk the chain backward from the symptom"
technique, unrelated to and not a wrapper around Python's ``traceback``
module.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..exceptions import ValidationError
from ..models import Confidence
from ..numbers import require_nonblank_str
from .base import RootCauseArtifact, RootCauseStrategyName, require_evidence_ids


@dataclass(frozen=True, slots=True)
class TraceStep:
    state_description: str
    evidence_ids: tuple[str, ...] = ()
    caused_by: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "state_description", require_nonblank_str(self.state_description, name="trace_step.state_description")
        )
        object.__setattr__(
            self, "evidence_ids", require_evidence_ids(self.evidence_ids, name="trace_step.evidence_ids")
        )
        if self.caused_by is not None:
            object.__setattr__(self, "caused_by", require_nonblank_str(self.caused_by, name="trace_step.caused_by"))


@dataclass(frozen=True, slots=True)
class TraceBackResult:
    observed_bad_state: str
    steps: tuple[TraceStep, ...]
    origin_confidence: Confidence = Confidence.LOW

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "observed_bad_state",
            require_nonblank_str(self.observed_bad_state, name="traceback.observed_bad_state"),
        )
        if not isinstance(self.steps, tuple) or not self.steps:
            raise ValidationError("traceback.steps must be a non-empty tuple, ordered observed -> origin")
        if not all(isinstance(s, TraceStep) for s in self.steps):
            raise ValidationError("traceback.steps entries must be TraceStep")
        if self.steps[-1].caused_by is not None:
            raise ValidationError("traceback.steps[-1] (the origin) must have caused_by=None")
        if not isinstance(self.origin_confidence, Confidence):
            raise ValidationError("traceback.origin_confidence must be a Confidence")

    def to_artifact(self) -> RootCauseArtifact:
        origin = self.steps[-1]
        return RootCauseArtifact(
            strategy=RootCauseStrategyName.TRACEBACK,
            problem=self.observed_bad_state,
            summary=f"traced back {len(self.steps)} step(s) to origin: {origin.state_description}",
            confidence=self.origin_confidence,
            data={
                "steps": [
                    {
                        "state_description": s.state_description,
                        "evidence_ids": list(s.evidence_ids),
                        "caused_by": s.caused_by,
                    }
                    for s in self.steps
                ]
            },
        )
