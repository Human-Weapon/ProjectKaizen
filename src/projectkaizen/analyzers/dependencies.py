"""DependencyAnalyzer: conservative, network-free dependency heuristics.

Parses ``pyproject.toml``'s ``dependencies = [...]`` array with a small
regex-based extractor (kept dependency-free rather than requiring
``tomllib``, which is 3.11+ only and this project supports 3.10). Checks:
duplicate dependency names, and unpinned VCS dependencies. Never resolves,
installs, or contacts a package index.
"""

from __future__ import annotations

import re

from ..config import KaizenConfig
from ..models import AnalysisResult, Confidence, Severity
from ..walker import WalkResult, read_text_bounded
from ._shared import complete, make_evidence, make_finding

ANALYZER_NAME = "DependencyAnalyzer"
_DEPENDENCIES_BLOCK_RE = re.compile(r"dependencies\s*=\s*\[(.*?)\]", re.DOTALL)
_ENTRY_RE = re.compile(r'"([^"]+)"|\'([^\']+)\'')
_NAME_RE = re.compile(r"^[A-Za-z0-9_.-]+")


def _extract_dependencies(pyproject_text: str) -> list[str]:
    match = _DEPENDENCIES_BLOCK_RE.search(pyproject_text)
    if not match:
        return []
    entries = []
    for m in _ENTRY_RE.finditer(match.group(1)):
        entries.append(m.group(1) or m.group(2))
    return entries


def analyze(walk: WalkResult, *, config: KaizenConfig, project_area_id: str = "root") -> AnalysisResult:
    pyproject = next((f for f in walk.files if f.relative_path == "pyproject.toml"), None)
    if pyproject is None:
        return complete(ANALYZER_NAME, [])

    try:
        text = read_text_bounded(pyproject.absolute_path, max_bytes=config.walker_max_bytes_per_file).text
    except OSError:
        return complete(ANALYZER_NAME, [])

    deps = _extract_dependencies(text)
    findings = []

    seen: dict[str, str] = {}
    duplicates: set[str] = set()
    for entry in deps:
        name_match = _NAME_RE.match(entry.strip())
        if not name_match:
            continue
        key = name_match.group(0).lower()
        if key in seen and seen[key] != entry:
            duplicates.add(key)
        seen[key] = entry

    if duplicates:
        findings.append(
            make_finding(
                analyzer=ANALYZER_NAME,
                project_area_id=project_area_id,
                title="duplicate dependency declarations",
                description=f"pyproject.toml declares the same dependency name more than once: {sorted(duplicates)}",
                evidence=(
                    make_evidence(ANALYZER_NAME, "duplicate_dependency", str(sorted(duplicates)), "pyproject.toml"),
                ),
                severity=Severity.LOW,
                confidence=Confidence.MEDIUM,
                affected_paths=("pyproject.toml",),
                estimated_effort="small",
                expected_impact="build_reliability",
                tags=("dependencies", "duplicate"),
            )
        )

    unpinned_vcs = [d for d in deps if ("git+" in d or d.startswith("http")) and "@" not in d.split("git+", 1)[-1]]
    if unpinned_vcs:
        findings.append(
            make_finding(
                analyzer=ANALYZER_NAME,
                project_area_id=project_area_id,
                title="unpinned VCS/URL dependency",
                description=(
                    f"{len(unpinned_vcs)} dependency URL(s) without a pinned ref: {unpinned_vcs[:10]}; "
                    "these can change contents underneath a build without any version bump."
                ),
                evidence=(make_evidence(ANALYZER_NAME, "unpinned_vcs", str(unpinned_vcs[:10]), "pyproject.toml"),),
                severity=Severity.MEDIUM,
                confidence=Confidence.MEDIUM,
                affected_paths=("pyproject.toml",),
                estimated_effort="small",
                expected_impact="build_reproducibility",
                tags=("dependencies", "reproducibility"),
            )
        )

    return complete(ANALYZER_NAME, findings)
