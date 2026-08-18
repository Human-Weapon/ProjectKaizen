"""Orchestrates scope resolution, diffing, contract comparison, and the
operational checklist into one ReadinessReport.

Outcome precedence: any BLOCKED finding wins outright; otherwise any
NEEDS_CONFIRMATION (or an unresolved scope) yields NEEDS_CONFIRMATION;
only a fully resolved scope with zero findings reaches NO_BLOCKER_FOUND —
which is never claimed to mean "safe" (spec section 20).
"""

from __future__ import annotations

from ..models import Confidence
from .checklist import run_operational_checklist
from .contracts import compare_contracts
from .diff import compute_changed_files
from .models import ReadinessOutcome, ReadinessReport, ReleaseFindingStatus, ReleaseScope, ScopeConfidence


def evaluate_readiness(project_root: str, *, scope: ReleaseScope, timeout_seconds: float = 15.0) -> ReadinessReport:
    if scope.confidence == ScopeConfidence.NO_BASELINE or scope.base is None:
        return ReadinessReport(
            scope=scope,
            changed_file_count=0,
            findings=(),
            outcome=ReadinessOutcome.NEEDS_CONFIRMATION,
            rationale=f"no resolvable baseline: {scope.rationale}",
            confidence=Confidence.LOW,
        )

    changed_files = compute_changed_files(
        project_root, base_sha=scope.base.sha, target_sha=scope.target.sha, timeout_seconds=timeout_seconds
    )
    checklist_findings = run_operational_checklist(changed_files)
    contract_findings = compare_contracts(
        project_root, base_sha=scope.base.sha, target_sha=scope.target.sha, timeout_seconds=timeout_seconds
    )
    all_findings = checklist_findings + contract_findings

    if any(f.status == ReleaseFindingStatus.BLOCKED for f in all_findings):
        blocked = [f.title for f in all_findings if f.status == ReleaseFindingStatus.BLOCKED]
        outcome = ReadinessOutcome.BLOCKED
        rationale = f"{len(blocked)} blocking finding(s): {blocked}"
    elif scope.dirty_worktree:
        outcome = ReadinessOutcome.NEEDS_CONFIRMATION
        rationale = "worktree has uncommitted changes; target is not a clean, reproducible state"
    elif any(f.status == ReleaseFindingStatus.NEEDS_CONFIRMATION for f in all_findings):
        outcome = ReadinessOutcome.NEEDS_CONFIRMATION
        rationale = f"{len(all_findings)} item(s) need human confirmation before release"
    else:
        outcome = ReadinessOutcome.NO_BLOCKER_FOUND
        rationale = (
            f"{len(changed_files)} file(s) changed; no blocker or confirmation-worthy signal found "
            "(this reflects what was checked, not a safety guarantee)"
        )

    confidence = Confidence.HIGH if scope.confidence == ScopeConfidence.EXPLICIT else Confidence.MEDIUM
    return ReadinessReport(
        scope=scope,
        changed_file_count=len(changed_files),
        findings=all_findings,
        outcome=outcome,
        rationale=rationale,
        confidence=confidence,
    )
