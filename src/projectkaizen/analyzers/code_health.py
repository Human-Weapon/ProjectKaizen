"""CodeHealthAnalyzer: small deterministic code-smell heuristics.

Not a full linter — see README limitations. Checks: oversized functions
(crude indentation-based body length), TODO/FIXME markers, and overly broad
``except`` clauses.
"""

from __future__ import annotations

import re

from ..config import KaizenConfig
from ..models import AnalysisResult, Confidence, Severity
from ..walker import WalkResult
from ._shared import complete, make_evidence, make_finding, read_files_text

ANALYZER_NAME = "CodeHealthAnalyzer"
OVERSIZED_FUNCTION_LINES = 80

_DEF_RE = re.compile(r"^( *)def\s+(\w+)\s*\(")
_TODO_RE = re.compile(r"#\s*(TODO|FIXME|XXX)\b", re.IGNORECASE)
_BROAD_EXCEPT_RE = re.compile(r"^\s*except\s*(Exception)?\s*:\s*$")


def _find_oversized_functions(path: str, text: str) -> list[tuple[str, int]]:
    lines = text.splitlines()
    hits: list[tuple[str, int]] = []
    i = 0
    while i < len(lines):
        match = _DEF_RE.match(lines[i])
        if not match:
            i += 1
            continue
        indent = len(match.group(1))
        name = match.group(2)
        body_len = 0
        j = i + 1
        while j < len(lines):
            line = lines[j]
            if line.strip() == "":
                body_len += 1
                j += 1
                continue
            current_indent = len(line) - len(line.lstrip(" "))
            if current_indent <= indent:
                break
            body_len += 1
            j += 1
        if body_len > OVERSIZED_FUNCTION_LINES:
            hits.append((name, body_len))
        i = j if j > i else i + 1
    return hits


def analyze(walk: WalkResult, *, config: KaizenConfig, project_area_id: str = "root") -> AnalysisResult:
    findings = []
    py_files = read_files_text(walk, suffixes=(".py",), max_bytes_per_file=config.walker_max_bytes_per_file)

    for path, text in sorted(py_files.items()):
        for name, body_len in _find_oversized_functions(path, text):
            findings.append(
                make_finding(
                    analyzer=ANALYZER_NAME,
                    project_area_id=project_area_id,
                    title=f"oversized function {name} in {path}",
                    description=f"function {name} in {path} has ~{body_len} body lines (> {OVERSIZED_FUNCTION_LINES}).",
                    evidence=(make_evidence(ANALYZER_NAME, "function_length", f"{body_len} lines", path),),
                    severity=Severity.LOW,
                    confidence=Confidence.MEDIUM,
                    affected_paths=(path,),
                    estimated_effort="medium",
                    expected_impact="maintainability",
                    tags=("code_health", "size"),
                )
            )

        todo_lines = [i + 1 for i, line in enumerate(text.splitlines()) if _TODO_RE.search(line)]
        if todo_lines:
            findings.append(
                make_finding(
                    analyzer=ANALYZER_NAME,
                    project_area_id=project_area_id,
                    title=f"TODO/FIXME markers in {path}",
                    description=f"{len(todo_lines)} TODO/FIXME/XXX marker(s) in {path} at lines {todo_lines[:10]}.",
                    evidence=(make_evidence(ANALYZER_NAME, "todo_marker", f"{len(todo_lines)} markers", path),),
                    severity=Severity.INFO,
                    confidence=Confidence.HIGH,
                    affected_paths=(path,),
                    estimated_effort="small",
                    expected_impact="maintainability",
                    tags=("code_health", "todo"),
                )
            )

        broad_except_lines = [i + 1 for i, line in enumerate(text.splitlines()) if _BROAD_EXCEPT_RE.match(line)]
        if broad_except_lines:
            findings.append(
                make_finding(
                    analyzer=ANALYZER_NAME,
                    project_area_id=project_area_id,
                    title=f"overly broad except clause in {path}",
                    description=(
                        f"{len(broad_except_lines)} bare/broad `except` clause(s) in {path} at lines "
                        f"{broad_except_lines[:10]}; these can silently swallow unrelated errors."
                    ),
                    evidence=(
                        make_evidence(ANALYZER_NAME, "broad_except", f"{len(broad_except_lines)} occurrences", path),
                    ),
                    severity=Severity.MEDIUM,
                    confidence=Confidence.MEDIUM,
                    affected_paths=(path,),
                    estimated_effort="small",
                    expected_impact="reliability",
                    tags=("code_health", "error_handling"),
                )
            )

    return complete(ANALYZER_NAME, findings)
