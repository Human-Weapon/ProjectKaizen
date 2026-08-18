"""A3 problem-solving report: the classic seven-field structure."""

from __future__ import annotations

from dataclasses import dataclass

from ..models import Confidence
from ..numbers import require_nonblank_str
from .base import RootCauseArtifact, RootCauseStrategyName


@dataclass(frozen=True, slots=True)
class A3Result:
    problem: str
    current_condition: str
    target_condition: str
    root_cause: str
    countermeasure: str
    verification: str
    follow_up: str = ""
    confidence: Confidence = Confidence.LOW

    def __post_init__(self) -> None:
        object.__setattr__(self, "problem", require_nonblank_str(self.problem, name="a3.problem"))
        object.__setattr__(
            self, "current_condition", require_nonblank_str(self.current_condition, name="a3.current_condition")
        )
        object.__setattr__(
            self, "target_condition", require_nonblank_str(self.target_condition, name="a3.target_condition")
        )
        object.__setattr__(self, "root_cause", require_nonblank_str(self.root_cause, name="a3.root_cause"))
        object.__setattr__(self, "countermeasure", require_nonblank_str(self.countermeasure, name="a3.countermeasure"))
        object.__setattr__(self, "verification", require_nonblank_str(self.verification, name="a3.verification"))

    def to_artifact(self) -> RootCauseArtifact:
        return RootCauseArtifact(
            strategy=RootCauseStrategyName.A3,
            problem=self.problem,
            summary=f"root cause: {self.root_cause}; countermeasure: {self.countermeasure}",
            confidence=self.confidence,
            data={
                "current_condition": self.current_condition,
                "target_condition": self.target_condition,
                "root_cause": self.root_cause,
                "countermeasure": self.countermeasure,
                "verification": self.verification,
                "follow_up": self.follow_up,
            },
        )
