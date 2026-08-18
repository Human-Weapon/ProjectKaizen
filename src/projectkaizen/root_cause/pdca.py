"""PDCA (Plan-Do-Check-Act) cycle record.

ProjectKaizen may PLAN a structured experiment and record what happened; it
never mutates source code itself (no module here executes anything —
that stays the caller's responsibility, same as verification commands
elsewhere in this project).
"""

from __future__ import annotations

from dataclasses import dataclass

from ..models import Confidence
from ..numbers import require_nonblank_str
from .base import RootCauseArtifact, RootCauseStrategyName


@dataclass(frozen=True, slots=True)
class PdcaCycle:
    plan: str
    do: str
    check: str
    act: str
    outcome: str = ""
    confidence: Confidence = Confidence.LOW

    def __post_init__(self) -> None:
        object.__setattr__(self, "plan", require_nonblank_str(self.plan, name="pdca.plan"))
        object.__setattr__(self, "do", require_nonblank_str(self.do, name="pdca.do"))
        object.__setattr__(self, "check", require_nonblank_str(self.check, name="pdca.check"))
        object.__setattr__(self, "act", require_nonblank_str(self.act, name="pdca.act"))

    def to_artifact(self) -> RootCauseArtifact:
        problem = self.plan
        summary = f"act: {self.act}" + (f" (outcome: {self.outcome})" if self.outcome else "")
        return RootCauseArtifact(
            strategy=RootCauseStrategyName.PDCA,
            problem=problem,
            summary=summary,
            confidence=self.confidence,
            data={"plan": self.plan, "do": self.do, "check": self.check, "act": self.act, "outcome": self.outcome},
        )
