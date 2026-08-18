"""Shared contract for root-cause strategies.

ProjectKaizen has no LLM and does no semantic reasoning (see README
limitations). These modules do not *generate* a root-cause chain — they
validate and structure one that a human or an LLM-backed caller supplies,
so the result is a typed, serializable artifact instead of free-text prose.
The methodologies (Five Whys, Fishbone, A3, PDCA, TraceBack) are generic and
not proprietary to any single source; this is a clean-room implementation of
each as a ProjectKaizen contract, not a port of any specific project's code.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import Any, Protocol, runtime_checkable

from ..exceptions import ValidationError
from ..jsonutil import to_jsonable
from ..models import Confidence
from ..numbers import require_nonblank_str, require_str_tuple


class RootCauseStrategyName(str, Enum):
    FIVE_WHYS = "five_whys"
    FISHBONE = "fishbone"
    A3 = "a3"
    PDCA = "pdca"
    TRACEBACK = "traceback"


@dataclass(frozen=True, slots=True)
class RootCauseArtifact:
    """A strategy-agnostic summary view, for callers that just want one shape."""

    strategy: RootCauseStrategyName
    problem: str
    summary: str
    confidence: Confidence
    data: Mapping[str, Any]

    def __post_init__(self) -> None:
        if not isinstance(self.strategy, RootCauseStrategyName):
            raise ValidationError("artifact.strategy must be a RootCauseStrategyName")
        object.__setattr__(self, "problem", require_nonblank_str(self.problem, name="artifact.problem"))
        object.__setattr__(self, "summary", require_nonblank_str(self.summary, name="artifact.summary"))
        if not isinstance(self.confidence, Confidence):
            raise ValidationError("artifact.confidence must be a Confidence")
        if not isinstance(self.data, Mapping):
            raise ValidationError("artifact.data must be a mapping")
        object.__setattr__(self, "data", MappingProxyType(dict(self.data)))

    def to_jsonable(self) -> dict[str, Any]:
        return {
            "strategy": self.strategy,
            "problem": self.problem,
            "summary": self.summary,
            "confidence": self.confidence,
            "data": to_jsonable(dict(self.data), name="artifact.data"),
        }


@runtime_checkable
class ProducesRootCauseArtifact(Protocol):
    def to_artifact(self) -> RootCauseArtifact: ...


def require_evidence_ids(value: Any, *, name: str) -> tuple[str, ...]:
    return require_str_tuple(value, name=name)


ALL_STRATEGIES: tuple[RootCauseStrategyName, ...] = tuple(RootCauseStrategyName)
