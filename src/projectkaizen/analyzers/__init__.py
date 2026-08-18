"""Analyzer registry.

Every analyzer is a plain function ``analyze(walk, *, config, project_area_id) ->
AnalysisResult``. Analyzers only read already-walked file metadata/bounded
text; they never import, execute, or install the target project (spec
section 25).
"""

from __future__ import annotations

from collections.abc import Callable

from ..config import KaizenConfig
from ..models import AnalysisResult
from ..walker import WalkResult
from . import (
    ai_agent_readiness,
    architecture,
    code_health,
    dependencies,
    developer_experience,
    documentation,
    repository_hygiene,
    test_health,
)

AnalyzerFunc = Callable[..., AnalysisResult]

ALL_ANALYZERS: dict[str, AnalyzerFunc] = {
    architecture.ANALYZER_NAME: architecture.analyze,
    code_health.ANALYZER_NAME: code_health.analyze,
    test_health.ANALYZER_NAME: test_health.analyze,
    documentation.ANALYZER_NAME: documentation.analyze,
    dependencies.ANALYZER_NAME: dependencies.analyze,
    repository_hygiene.ANALYZER_NAME: repository_hygiene.analyze,
    developer_experience.ANALYZER_NAME: developer_experience.analyze,
    ai_agent_readiness.ANALYZER_NAME: ai_agent_readiness.analyze,
}


def run_all(walk: WalkResult, *, config: KaizenConfig, project_area_id: str = "root") -> tuple[AnalysisResult, ...]:
    return tuple(
        ALL_ANALYZERS[name](walk, config=config, project_area_id=project_area_id) for name in sorted(ALL_ANALYZERS)
    )
