"""Five Whys: a structured, validated why-chain.

The chain does not have to reach exactly five steps — spec requirement:
"Do not force exactly five levels when evidence ends earlier." 1-5 steps are
accepted; a caller that has run out of evidence records why it stopped
rather than padding the chain.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..exceptions import ValidationError
from ..models import Confidence, RootCauseStatus
from ..numbers import require_nonblank_str
from .base import RootCauseArtifact, RootCauseStrategyName, require_evidence_ids

MAX_STEPS = 5


@dataclass(frozen=True, slots=True)
class WhyStep:
    question: str
    answer: str
    evidence_ids: tuple[str, ...] = ()
    confidence: Confidence = Confidence.LOW

    def __post_init__(self) -> None:
        object.__setattr__(self, "question", require_nonblank_str(self.question, name="why_step.question"))
        object.__setattr__(self, "answer", require_nonblank_str(self.answer, name="why_step.answer"))
        object.__setattr__(self, "evidence_ids", require_evidence_ids(self.evidence_ids, name="why_step.evidence_ids"))
        if not isinstance(self.confidence, Confidence):
            raise ValidationError("why_step.confidence must be a Confidence")


@dataclass(frozen=True, slots=True)
class FiveWhysResult:
    problem: str
    steps: tuple[WhyStep, ...]
    termination_reason: str
    root_cause_status: RootCauseStatus

    def __post_init__(self) -> None:
        object.__setattr__(self, "problem", require_nonblank_str(self.problem, name="five_whys.problem"))
        if not isinstance(self.steps, tuple) or not self.steps:
            raise ValidationError("five_whys.steps must be a non-empty tuple")
        if len(self.steps) > MAX_STEPS:
            raise ValidationError(f"five_whys.steps must have at most {MAX_STEPS} entries; got {len(self.steps)}")
        if not all(isinstance(s, WhyStep) for s in self.steps):
            raise ValidationError("five_whys.steps entries must be WhyStep")
        object.__setattr__(
            self,
            "termination_reason",
            require_nonblank_str(self.termination_reason, name="five_whys.termination_reason"),
        )
        if not isinstance(self.root_cause_status, RootCauseStatus):
            raise ValidationError("five_whys.root_cause_status must be a RootCauseStatus")

    def to_artifact(self) -> RootCauseArtifact:
        last = self.steps[-1]
        return RootCauseArtifact(
            strategy=RootCauseStrategyName.FIVE_WHYS,
            problem=self.problem,
            summary=f"after {len(self.steps)} why-step(s): {last.answer} ({self.termination_reason})",
            confidence=last.confidence,
            data={
                "steps": [
                    {
                        "question": s.question,
                        "answer": s.answer,
                        "evidence_ids": list(s.evidence_ids),
                        "confidence": s.confidence.value,
                    }
                    for s in self.steps
                ],
                "termination_reason": self.termination_reason,
                "root_cause_status": self.root_cause_status.value,
            },
        )
