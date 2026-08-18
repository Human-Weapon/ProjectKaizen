"""Shared helpers for analyzers.

Analyzers never import or execute target-project code (spec section 25):
everything here is plain-text/regex heuristics over bytes read through
:func:`projectkaizen.walker.read_text_bounded`, plus filesystem metadata.
"""

from __future__ import annotations

from collections.abc import Iterable

from ..fingerprint import deterministic_id
from ..models import AnalysisResult, AnalysisStatus, Confidence, Evidence, Finding, Severity
from ..walker import WalkResult, read_text_bounded


def make_evidence(analyzer: str, kind: str, description: str, source: str, *, data: dict | None = None) -> Evidence:
    eid = deterministic_id("evidence", analyzer, kind, description, source)
    return Evidence(id=eid, kind=kind, description=description, source=source, data=data or {})


def make_finding(
    *,
    analyzer: str,
    project_area_id: str,
    title: str,
    description: str,
    evidence: tuple[Evidence, ...],
    severity: Severity,
    confidence: Confidence,
    affected_paths: tuple[str, ...] = (),
    estimated_effort: str = "small",
    expected_impact: str = "unknown",
    implementation_risk: str = "low",
    tags: tuple[str, ...] = (),
) -> Finding:
    fid = deterministic_id("finding", analyzer, project_area_id, title, *sorted(affected_paths))
    return Finding(
        id=fid,
        project_area_id=project_area_id,
        title=title,
        description=description,
        evidence=evidence,
        severity=severity,
        confidence=confidence,
        affected_paths=affected_paths,
        estimated_effort=estimated_effort,
        expected_impact=expected_impact,
        implementation_risk=implementation_risk,
        source=analyzer,
        tags=tags,
    )


def complete(analyzer: str, findings: Iterable[Finding]) -> AnalysisResult:
    return AnalysisResult(analyzer=analyzer, status=AnalysisStatus.COMPLETE, findings=tuple(findings))


def incomplete(analyzer: str, findings: Iterable[Finding], reasons: tuple[str, ...]) -> AnalysisResult:
    return AnalysisResult(
        analyzer=analyzer,
        status=AnalysisStatus.ANALYSIS_INCOMPLETE,
        findings=tuple(findings),
        incomplete_reasons=reasons,
    )


def read_files_text(walk: WalkResult, *, suffixes: tuple[str, ...], max_bytes_per_file: int) -> dict[str, str]:
    """Read matching walked files as bounded text, skipping unreadable ones."""
    out: dict[str, str] = {}
    for f in walk.files:
        if suffixes and not f.relative_path.endswith(suffixes):
            continue
        try:
            result = read_text_bounded(f.absolute_path, max_bytes=max_bytes_per_file)
        except OSError:
            continue
        out[f.relative_path] = result.text
    return out
