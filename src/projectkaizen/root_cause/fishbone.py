"""Fishbone (Ishikawa) diagram: categorized cause hypotheses.

Categories default to the generic set (people/process/tools/environment/
inputs/measurement) but are plain strings, not an enum, so project-specific
categories are equally valid — the spec explicitly allows this.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..exceptions import ValidationError
from ..models import Confidence, confidence_weight
from ..numbers import require_nonblank_str
from .base import RootCauseArtifact, RootCauseStrategyName, require_evidence_ids

GENERIC_CATEGORIES: tuple[str, ...] = ("people", "process", "tools", "environment", "inputs", "measurement")


@dataclass(frozen=True, slots=True)
class FishboneCause:
    category: str
    hypothesis: str
    evidence_ids: tuple[str, ...] = ()
    confidence: Confidence = Confidence.LOW

    def __post_init__(self) -> None:
        object.__setattr__(self, "category", require_nonblank_str(self.category, name="fishbone_cause.category"))
        object.__setattr__(self, "hypothesis", require_nonblank_str(self.hypothesis, name="fishbone_cause.hypothesis"))
        object.__setattr__(
            self, "evidence_ids", require_evidence_ids(self.evidence_ids, name="fishbone_cause.evidence_ids")
        )
        if not isinstance(self.confidence, Confidence):
            raise ValidationError("fishbone_cause.confidence must be a Confidence")


@dataclass(frozen=True, slots=True)
class FishboneResult:
    problem: str
    causes: tuple[FishboneCause, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "problem", require_nonblank_str(self.problem, name="fishbone.problem"))
        if not isinstance(self.causes, tuple) or not self.causes:
            raise ValidationError("fishbone.causes must be a non-empty tuple")
        if not all(isinstance(c, FishboneCause) for c in self.causes):
            raise ValidationError("fishbone.causes entries must be FishboneCause")

    def to_artifact(self) -> RootCauseArtifact:
        strongest = max(self.causes, key=lambda c: confidence_weight(c.confidence))
        categories = sorted({c.category for c in self.causes})
        return RootCauseArtifact(
            strategy=RootCauseStrategyName.FISHBONE,
            problem=self.problem,
            summary=f"{len(self.causes)} hypothesis(es) across categories {categories}",
            confidence=strongest.confidence,
            data={
                "causes": [
                    {
                        "category": c.category,
                        "hypothesis": c.hypothesis,
                        "evidence_ids": list(c.evidence_ids),
                        "confidence": c.confidence.value,
                    }
                    for c in self.causes
                ]
            },
        )
