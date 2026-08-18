from __future__ import annotations

import pytest

from projectkaizen.config import KaizenConfig
from projectkaizen.models import Confidence, Evidence, Finding, Severity


@pytest.fixture
def config() -> KaizenConfig:
    return KaizenConfig()


def make_finding(
    id: str = "f1",
    *,
    severity: Severity = Severity.MEDIUM,
    confidence: Confidence = Confidence.MEDIUM,
    project_area_id: str = "pa",
    evidence: tuple[Evidence, ...] = (),
) -> Finding:
    return Finding(
        id=id,
        project_area_id=project_area_id,
        title=f"title-{id}",
        description=f"description-{id}",
        evidence=evidence,
        severity=severity,
        confidence=confidence,
    )
