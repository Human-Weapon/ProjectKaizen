"""AIAgentReadinessAnalyzer: small deterministic agent-friendliness heuristics.

Checks: missing agent-facing instructions file, and non-deterministic calls
(``random.random()``, ``datetime.now()``) in source without an obvious seed,
which reduce reproducibility for agents re-running the same task. This does
not duplicate PromptGraph's context-graph/requirements work — it only flags
structural repository readiness.
"""

from __future__ import annotations

import re

from ..config import KaizenConfig
from ..models import AnalysisResult, Confidence, Severity
from ..walker import WalkResult
from ._shared import complete, make_evidence, make_finding, read_files_text

ANALYZER_NAME = "AIAgentReadinessAnalyzer"
_AGENT_DOC_NAMES = {"agents.md", "claude.md", "copilot-instructions.md"}
_NONDETERMINISTIC_RE = re.compile(r"\b(random\.random|random\.randint|datetime\.now|time\.time)\s*\(")


def analyze(walk: WalkResult, *, config: KaizenConfig, project_area_id: str = "root") -> AnalysisResult:
    findings = []
    relative_paths = {f.relative_path for f in walk.files}
    has_agent_doc = any(
        p.lower() in _AGENT_DOC_NAMES or p.lower() == ".github/copilot-instructions.md" for p in relative_paths
    )
    if not has_agent_doc:
        findings.append(
            make_finding(
                analyzer=ANALYZER_NAME,
                project_area_id=project_area_id,
                title="no agent-facing instructions file",
                description=(
                    "No AGENTS.md/CLAUDE.md/.github/copilot-instructions.md found; AI agents working on this "
                    "repo have no canonical place to learn project-specific conventions and commands."
                ),
                evidence=(make_evidence(ANALYZER_NAME, "missing_file", "no agent doc", "walk"),),
                severity=Severity.LOW,
                confidence=Confidence.HIGH,
                estimated_effort="small",
                expected_impact="ai_agent_productivity",
                tags=("ai_agent_readiness", "instructions"),
            )
        )

    py_files = read_files_text(walk, suffixes=(".py",), max_bytes_per_file=config.walker_max_bytes_per_file)
    nondeterministic_hits: dict[str, int] = {}
    for path, text in py_files.items():
        if "/tests/" in f"/{path}" or path.startswith("tests/") or path.rsplit("/", 1)[-1].startswith("test_"):
            continue
        count = len(_NONDETERMINISTIC_RE.findall(text))
        if count:
            nondeterministic_hits[path] = count

    if nondeterministic_hits:
        affected = tuple(sorted(nondeterministic_hits))
        total = sum(nondeterministic_hits.values())
        findings.append(
            make_finding(
                analyzer=ANALYZER_NAME,
                project_area_id=project_area_id,
                title="non-deterministic calls in production code",
                description=(
                    f"{total} call(s) to random/time-based functions across {len(affected)} file(s): "
                    f"{affected[:10]}; these reduce reproducibility for agents re-running the same task "
                    "and for ProjectKaizen's own determinism guarantees if this code feeds ids or ordering."
                ),
                evidence=(make_evidence(ANALYZER_NAME, "nondeterministic_call", f"{total} occurrences", "walk"),),
                severity=Severity.INFO,
                confidence=Confidence.LOW,
                affected_paths=affected,
                estimated_effort="medium",
                expected_impact="reproducibility",
                tags=("ai_agent_readiness", "determinism"),
            )
        )

    return complete(ANALYZER_NAME, findings)
