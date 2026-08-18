"""Release readiness: is HEAD (or an explicit target) safe to release
relative to a base?

Answers with BLOCKED / NEEDS_CONFIRMATION / NO_BLOCKER_FOUND — never
"safe" or "guaranteed." See readiness.py for the outcome contract.
"""

from __future__ import annotations

from .checklist import run_operational_checklist
from .contracts import compare_contracts
from .diff import classify_change, compute_changed_files
from .models import (
    ChangeCategory,
    ChangedFile,
    ChangeType,
    ReadinessOutcome,
    ReadinessReport,
    ReleaseFinding,
    ReleaseFindingStatus,
    ReleaseRef,
    ReleaseScope,
    ScopeConfidence,
)
from .readiness import evaluate_readiness
from .scope import resolve_scope
from .tags import list_tags, parse_version_tag, resolve_latest_tag

__all__ = [
    "ChangeCategory",
    "ChangeType",
    "ChangedFile",
    "ReadinessOutcome",
    "ReadinessReport",
    "ReleaseFinding",
    "ReleaseFindingStatus",
    "ReleaseRef",
    "ReleaseScope",
    "ScopeConfidence",
    "classify_change",
    "compare_contracts",
    "compute_changed_files",
    "evaluate_readiness",
    "list_tags",
    "parse_version_tag",
    "resolve_latest_tag",
    "resolve_scope",
    "run_operational_checklist",
]
