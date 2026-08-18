"""TestHealthAnalyzer: small deterministic test-quality heuristics.

Checks: source modules with no naming-convention-matched test file,
skipped tests, and tautological/weak assertions (``assert True``).
"""

from __future__ import annotations

import re

from ..config import KaizenConfig
from ..models import AnalysisResult, Confidence, Severity
from ..walker import WalkResult
from ._shared import complete, make_evidence, make_finding, read_files_text

ANALYZER_NAME = "TestHealthAnalyzer"

_SKIP_RE = re.compile(r"@pytest\.mark\.skip|pytest\.skip\(|unittest\.skip")
_WEAK_ASSERT_RE = re.compile(r"^\s*assert\s+(True|1)\s*(#.*)?$")


def _is_test_file(path: str) -> bool:
    name = path.rsplit("/", 1)[-1]
    return name.startswith("test_") or name.endswith("_test.py") or "/tests/" in f"/{path}" or path.startswith("tests/")


def analyze(walk: WalkResult, *, config: KaizenConfig, project_area_id: str = "root") -> AnalysisResult:
    findings = []
    py_files = read_files_text(walk, suffixes=(".py",), max_bytes_per_file=config.walker_max_bytes_per_file)

    test_files = {p for p in py_files if _is_test_file(p)}
    source_files = {p for p in py_files if not _is_test_file(p) and not p.endswith("__init__.py")}

    test_stems = {
        p.rsplit("/", 1)[-1].removeprefix("test_").removesuffix("_test.py").removesuffix(".py") for p in test_files
    }
    untested = []
    for path in sorted(source_files):
        stem = path.rsplit("/", 1)[-1].removesuffix(".py")
        if stem not in test_stems:
            untested.append(path)

    if untested:
        findings.append(
            make_finding(
                analyzer=ANALYZER_NAME,
                project_area_id=project_area_id,
                title="source modules without a matching test file",
                description=(
                    f"{len(untested)} source module(s) have no test_<name>.py / <name>_test.py counterpart: "
                    f"{untested[:10]}"
                ),
                evidence=(make_evidence(ANALYZER_NAME, "untested_modules", f"{len(untested)} modules", "walk"),),
                severity=Severity.MEDIUM,
                confidence=Confidence.LOW,
                affected_paths=tuple(untested),
                estimated_effort="large",
                expected_impact="regression_safety",
                tags=("test_health", "coverage"),
            )
        )

    for path in sorted(test_files):
        text = py_files[path]
        skip_lines = [i + 1 for i, line in enumerate(text.splitlines()) if _SKIP_RE.search(line)]
        if skip_lines:
            findings.append(
                make_finding(
                    analyzer=ANALYZER_NAME,
                    project_area_id=project_area_id,
                    title=f"skipped tests in {path}",
                    description=f"{len(skip_lines)} skipped test marker(s) in {path} at lines {skip_lines[:10]}.",
                    evidence=(make_evidence(ANALYZER_NAME, "skipped_test", f"{len(skip_lines)} occurrences", path),),
                    severity=Severity.LOW,
                    confidence=Confidence.HIGH,
                    affected_paths=(path,),
                    estimated_effort="small",
                    expected_impact="regression_safety",
                    tags=("test_health", "skipped"),
                )
            )

        weak_lines = [i + 1 for i, line in enumerate(text.splitlines()) if _WEAK_ASSERT_RE.match(line)]
        if weak_lines:
            findings.append(
                make_finding(
                    analyzer=ANALYZER_NAME,
                    project_area_id=project_area_id,
                    title=f"tautological assertion in {path}",
                    description=(
                        f"{len(weak_lines)} `assert True`/`assert 1` (always-true) assertion(s) in {path} at "
                        f"lines {weak_lines[:10]}; these never fail and provide no coverage."
                    ),
                    evidence=(make_evidence(ANALYZER_NAME, "weak_assertion", f"{len(weak_lines)} occurrences", path),),
                    severity=Severity.MEDIUM,
                    confidence=Confidence.HIGH,
                    affected_paths=(path,),
                    estimated_effort="small",
                    expected_impact="regression_safety",
                    tags=("test_health", "tautological"),
                )
            )

    return complete(ANALYZER_NAME, findings)
