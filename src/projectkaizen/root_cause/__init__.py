"""Root-cause strategy layer: structured, validated containers for a
root-cause investigation a human or LLM-backed caller performs.

Clean-room implementations of generic, non-proprietary methodologies
(Five Whys, Fishbone/Ishikawa, A3, PDCA, TraceBack) — see
docs/oss-reuse-manifest.md for the provenance note on why these are
independent implementations rather than ports of any specific project.
"""

from __future__ import annotations

from .a3 import A3Result
from .base import ALL_STRATEGIES, ProducesRootCauseArtifact, RootCauseArtifact, RootCauseStrategyName
from .fishbone import FishboneCause, FishboneResult
from .five_whys import FiveWhysResult, WhyStep
from .pdca import PdcaCycle
from .traceback import TraceBackResult, TraceStep

__all__ = [
    "ALL_STRATEGIES",
    "A3Result",
    "FishboneCause",
    "FishboneResult",
    "FiveWhysResult",
    "PdcaCycle",
    "ProducesRootCauseArtifact",
    "RootCauseArtifact",
    "RootCauseStrategyName",
    "TraceBackResult",
    "TraceStep",
    "WhyStep",
]
