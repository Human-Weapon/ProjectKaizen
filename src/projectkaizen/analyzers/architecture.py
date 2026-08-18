"""ArchitectureAnalyzer: small, deterministic structural heuristics.

Checks: oversized modules (line count), and mixed top-level package layout
(both a flat top-level package dir and a ``src/`` layout present at once,
a common source of import-path confusion). Not a full architecture audit —
see README limitations.
"""

from __future__ import annotations

from ..config import KaizenConfig
from ..models import AnalysisResult, Confidence, Severity
from ..walker import WalkResult
from ._shared import complete, make_evidence, make_finding, read_files_text

ANALYZER_NAME = "ArchitectureAnalyzer"
OVERSIZED_MODULE_LINES = 600


def analyze(walk: WalkResult, *, config: KaizenConfig, project_area_id: str = "root") -> AnalysisResult:
    findings = []
    py_files = read_files_text(walk, suffixes=(".py",), max_bytes_per_file=config.walker_max_bytes_per_file)

    for path, text in sorted(py_files.items()):
        line_count = text.count("\n") + 1
        if line_count > OVERSIZED_MODULE_LINES:
            findings.append(
                make_finding(
                    analyzer=ANALYZER_NAME,
                    project_area_id=project_area_id,
                    title=f"oversized module: {path}",
                    description=(
                        f"{path} has {line_count} lines (> {OVERSIZED_MODULE_LINES}); large modules are "
                        "harder to navigate and often mix unrelated responsibilities."
                    ),
                    evidence=(
                        make_evidence(
                            ANALYZER_NAME, "line_count", f"{line_count} lines", path, data={"line_count": line_count}
                        ),
                    ),
                    severity=Severity.LOW,
                    confidence=Confidence.HIGH,
                    affected_paths=(path,),
                    estimated_effort="medium",
                    expected_impact="maintainability",
                    tags=("architecture", "size"),
                )
            )

    top_level_dirs = {p.relative_path.split("/", 1)[0] for p in walk.files if "/" in p.relative_path}
    has_src_layout = "src" in top_level_dirs
    flat_package_dirs = {
        d
        for d in top_level_dirs
        if d not in {"src", "tests", "test", "docs", "examples", "scripts", ".github"} and not d.startswith(".")
    }
    if has_src_layout and flat_package_dirs:
        findings.append(
            make_finding(
                analyzer=ANALYZER_NAME,
                project_area_id=project_area_id,
                title="mixed src-layout and flat top-level packages",
                description=(
                    "Both a src/ layout and flat top-level package directories were found: "
                    f"{sorted(flat_package_dirs)}. Mixing layouts confuses import resolution and packaging."
                ),
                evidence=(
                    make_evidence(
                        ANALYZER_NAME,
                        "directory_layout",
                        f"top-level dirs: {sorted(top_level_dirs)}",
                        "walk",
                    ),
                ),
                severity=Severity.MEDIUM,
                confidence=Confidence.MEDIUM,
                estimated_effort="large",
                expected_impact="maintainability",
                tags=("architecture", "layout"),
            )
        )

    return complete(ANALYZER_NAME, findings)
