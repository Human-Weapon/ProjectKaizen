"""OutputBudget enforcement and priority-aware compression.

Principle (spec sections 34-38): MINIMUM SUFFICIENT RESPONSE, NO OUTPUT
WITHOUT DECISION VALUE. Concise is the default. When items must be cut,
critical-severity findings are never among the casualties — they are kept
even if that means showing more than ``max_findings_shown``. Full detail is
never destroyed, only hidden from the concise view; ``--full``/DETAILED
mode surfaces everything the concise view derived from.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from enum import Enum
from typing import Generic, TypeVar

from .models import Evidence, Finding, OutputBudget, Severity

T = TypeVar("T")

#: multiplier applied to each OutputBudget field for STANDARD mode
STANDARD_MODE_MULTIPLIER = 3
#: effectively "unbounded" cap used for DETAILED/full mode
DETAILED_MODE_CAP = 100_000


class OutputMode(str, Enum):
    CONCISE = "concise"
    STANDARD = "standard"
    DETAILED = "detailed"


def effective_budget(base: OutputBudget, mode: OutputMode) -> OutputBudget:
    if mode == OutputMode.CONCISE:
        return base
    if mode == OutputMode.STANDARD:
        return OutputBudget(
            max_findings_shown=base.max_findings_shown * STANDARD_MODE_MULTIPLIER,
            max_improvements_shown=base.max_improvements_shown * STANDARD_MODE_MULTIPLIER,
            max_evidence_items_per_finding=base.max_evidence_items_per_finding * STANDARD_MODE_MULTIPLIER,
            max_history_items_shown=base.max_history_items_shown * STANDARD_MODE_MULTIPLIER,
            max_lessons_shown=base.max_lessons_shown * STANDARD_MODE_MULTIPLIER,
        )
    return OutputBudget(
        max_findings_shown=DETAILED_MODE_CAP,
        max_improvements_shown=DETAILED_MODE_CAP,
        max_evidence_items_per_finding=DETAILED_MODE_CAP,
        max_history_items_shown=DETAILED_MODE_CAP,
        max_lessons_shown=DETAILED_MODE_CAP,
    )


@dataclass(frozen=True, slots=True)
class Compressed(Generic[T]):
    shown: tuple[T, ...]
    total_count: int
    omitted_count: int
    forced_kept_count: int

    def summary(self, *, noun: str) -> str:
        if self.omitted_count == 0:
            return f"{self.total_count} {noun}"
        return f"{self.total_count} {noun}; showing top {len(self.shown)}"


def compress(
    items: Sequence[T],
    *,
    max_shown: int,
    must_keep: Callable[[T], bool] = lambda _item: False,
) -> Compressed[T]:
    """Keep the first ``max_shown`` items (assumed pre-sorted by priority),
    plus any item ``must_keep`` flags, in original relative order.
    """
    items = tuple(items)
    forced_idx = {i for i, item in enumerate(items) if must_keep(item)}
    head_idx = set(range(min(max_shown, len(items))))
    keep_idx = sorted(forced_idx | head_idx)
    shown = tuple(items[i] for i in keep_idx)
    return Compressed(
        shown=shown,
        total_count=len(items),
        omitted_count=len(items) - len(shown),
        forced_kept_count=len(forced_idx - head_idx),
    )


def is_critical(finding: Finding) -> bool:
    return finding.severity == Severity.CRITICAL


def compress_findings(findings: Sequence[Finding], *, budget: OutputBudget) -> Compressed[Finding]:
    """Findings are assumed pre-sorted by priority (see prioritize.rank_findings)."""
    return compress(findings, max_shown=budget.max_findings_shown, must_keep=is_critical)


def compress_evidence(evidence: Sequence[Evidence], *, budget: OutputBudget) -> Compressed[Evidence]:
    return compress(evidence, max_shown=budget.max_evidence_items_per_finding)


@dataclass(frozen=True, slots=True)
class FindingsDisplay:
    mode: OutputMode
    compressed: Compressed[Finding]
    evidence_by_finding: dict[str, Compressed[Evidence]]

    @property
    def summary(self) -> str:
        return self.compressed.summary(noun="findings detected")


def build_findings_display(findings: Sequence[Finding], *, budget: OutputBudget, mode: OutputMode) -> FindingsDisplay:
    eff = effective_budget(budget, mode)
    compressed = compress_findings(findings, budget=eff)
    evidence_by_finding = {f.id: compress_evidence(f.evidence, budget=eff) for f in compressed.shown}
    return FindingsDisplay(mode=mode, compressed=compressed, evidence_by_finding=evidence_by_finding)
