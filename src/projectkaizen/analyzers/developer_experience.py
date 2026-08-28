"""DeveloperExperienceAnalyzer: small deterministic DX heuristics.

Checks: missing pyproject.toml (no clear, standard way to install/build),
when Python product code makes packaging relevant, and missing CONTRIBUTING
guidance.
"""

from __future__ import annotations

from ..config import KaizenConfig
from ..models import AnalysisResult, Confidence, Severity
from ..walker import WalkResult
from ._shared import complete, make_evidence, make_finding

ANALYZER_NAME = "DeveloperExperienceAnalyzer"

# Python files under these directories are ordinarily auxiliary to another
# product. Their presence alone is not evidence that the inspected project
# should be distributed as a Python package.
_AUXILIARY_PYTHON_DIRS = frozenset(
    {
        "benchmark",
        "benchmarks",
        "docs",
        "examples",
        "scripts",
        "test",
        "tests",
        "tool",
        "tools",
    }
)


def _has_python_product_code(relative_paths: set[str]) -> bool:
    """Return whether the walk contains Python outside conventional tooling paths.

    This is deliberately an applicability gate, not a universal project-type
    classifier: a repository may contain multiple products. A Python file in
    product code is enough to make missing packaging actionable, while scripts
    solely under known auxiliary directories are not.
    """

    for path in relative_paths:
        if not path.endswith(".py"):
            continue
        parent_dirs = path.lower().split("/")[:-1]
        if not any(directory in _AUXILIARY_PYTHON_DIRS for directory in parent_dirs):
            return True
    return False


def analyze(walk: WalkResult, *, config: KaizenConfig, project_area_id: str = "root") -> AnalysisResult:
    findings = []
    relative_paths = {f.relative_path for f in walk.files}

    has_packaging_file = relative_paths & {"pyproject.toml", "setup.py", "setup.cfg"}
    if not has_packaging_file and _has_python_product_code(relative_paths):
        findings.append(
            make_finding(
                analyzer=ANALYZER_NAME,
                project_area_id=project_area_id,
                title="no standard Python packaging file",
                description=(
                    "No pyproject.toml/setup.py/setup.cfg found; contributors have no standard "
                    "install/build entry point."
                ),
                evidence=(make_evidence(ANALYZER_NAME, "missing_file", "no packaging file", "walk"),),
                severity=Severity.HIGH,
                confidence=Confidence.HIGH,
                estimated_effort="medium",
                expected_impact="contributor_onboarding",
                tags=("developer_experience", "packaging"),
            )
        )

    has_contributing = any(p.lower() in {"contributing.md", "contributing.rst"} for p in relative_paths)
    if not has_contributing:
        findings.append(
            make_finding(
                analyzer=ANALYZER_NAME,
                project_area_id=project_area_id,
                title="missing CONTRIBUTING guide",
                description="No CONTRIBUTING.md found; new contributors lack setup/testing/PR guidance.",
                evidence=(make_evidence(ANALYZER_NAME, "missing_file", "no CONTRIBUTING.md", "walk"),),
                severity=Severity.INFO,
                confidence=Confidence.HIGH,
                estimated_effort="small",
                expected_impact="contributor_onboarding",
                tags=("developer_experience", "docs"),
            )
        )

    return complete(ANALYZER_NAME, findings)
