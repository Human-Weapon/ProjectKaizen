"""DocumentationAnalyzer: small deterministic documentation heuristics.

Checks: missing README, and a README version string that disagrees with
``_version.py``. Does not perform semantic claim-checking — see README
limitations.
"""

from __future__ import annotations

import re

from ..config import KaizenConfig
from ..models import AnalysisResult, Confidence, Severity
from ..walker import WalkResult
from ._shared import complete, make_evidence, make_finding, read_files_text

ANALYZER_NAME = "DocumentationAnalyzer"
_VERSION_RE = re.compile(r'__version__\s*=\s*["\']([^"\']+)["\']')
_README_VERSION_RE = re.compile(r"\bv?(\d+\.\d+\.\d+)\b")


def analyze(walk: WalkResult, *, config: KaizenConfig, project_area_id: str = "root") -> AnalysisResult:
    findings = []
    readmes = [f for f in walk.files if f.relative_path.lower() in {"readme.md", "readme.rst", "readme.txt", "readme"}]

    if not readmes:
        findings.append(
            make_finding(
                analyzer=ANALYZER_NAME,
                project_area_id=project_area_id,
                title="missing README",
                description="No README.md/README.rst/README found at the project root.",
                evidence=(make_evidence(ANALYZER_NAME, "missing_file", "no README candidate found", "walk"),),
                severity=Severity.HIGH,
                confidence=Confidence.HIGH,
                estimated_effort="medium",
                expected_impact="onboarding",
                tags=("documentation", "readme"),
            )
        )
        return complete(ANALYZER_NAME, findings)

    all_text = read_files_text(walk, suffixes=(".py",), max_bytes_per_file=config.walker_max_bytes_per_file)
    version_files = {p: t for p, t in all_text.items() if p.endswith("_version.py")}
    declared_version = None
    for text in version_files.values():
        m = _VERSION_RE.search(text)
        if m:
            declared_version = m.group(1)
            break

    if declared_version:
        readme_path = sorted(readmes, key=lambda f: f.relative_path)[0]
        try:
            from ..walker import read_text_bounded

            readme_text = read_text_bounded(readme_path.absolute_path, max_bytes=config.walker_max_bytes_per_file).text
        except OSError:
            readme_text = ""
        mismatch_versions = set(_README_VERSION_RE.findall(readme_text)) - {declared_version}
        if mismatch_versions:
            findings.append(
                make_finding(
                    analyzer=ANALYZER_NAME,
                    project_area_id=project_area_id,
                    title="README version mentions disagree with package version",
                    description=(
                        f"package declares version {declared_version!r} but README mentions "
                        f"{sorted(mismatch_versions)}; this heuristic can false-positive on unrelated "
                        "version-shaped numbers (dates, dependency pins) and should be verified before acting."
                    ),
                    evidence=(
                        make_evidence(
                            ANALYZER_NAME, "version_mismatch", f"declared={declared_version}", readme_path.relative_path
                        ),
                    ),
                    severity=Severity.LOW,
                    confidence=Confidence.LOW,
                    affected_paths=(readme_path.relative_path,),
                    estimated_effort="small",
                    expected_impact="accuracy",
                    tags=("documentation", "version"),
                )
            )

    return complete(ANALYZER_NAME, findings)
