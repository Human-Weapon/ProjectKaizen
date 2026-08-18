"""Bounded, deterministic improvement history.

Each entry captures the full chain: Problem -> Evidence -> Root Cause ->
Failed Attempts -> Why They Failed -> Decision -> Solution -> Regression
Test -> Result -> Lesson. History does not grow without bound: once
``max_entries`` is reached, the oldest entry is evicted (FIFO) to make room
for the newest — eviction order is a documented policy, not an accident of
dict ordering.
"""

from __future__ import annotations

from dataclasses import dataclass

from .exceptions import ValidationError
from .numbers import require_nonblank_str, require_str_tuple


@dataclass(frozen=True, slots=True)
class HistoryEntry:
    id: str
    sequence: int
    improvement_id: str
    problem: str
    evidence_ids: tuple[str, ...]
    root_cause_id: str | None
    failed_attempts: tuple[str, ...]
    decision: str
    solution: str
    regression_test: str
    result: str
    lesson_id: str | None
    superseded_by: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", require_nonblank_str(self.id, name="history_entry.id"))
        if not isinstance(self.sequence, int) or isinstance(self.sequence, bool) or self.sequence < 0:
            raise ValidationError("history_entry.sequence must be a non-negative int")
        object.__setattr__(
            self, "improvement_id", require_nonblank_str(self.improvement_id, name="history_entry.improvement_id")
        )
        object.__setattr__(self, "problem", require_nonblank_str(self.problem, name="history_entry.problem"))
        object.__setattr__(
            self, "evidence_ids", require_str_tuple(self.evidence_ids, name="history_entry.evidence_ids")
        )
        object.__setattr__(
            self, "failed_attempts", require_str_tuple(self.failed_attempts, name="history_entry.failed_attempts")
        )
        object.__setattr__(self, "decision", require_nonblank_str(self.decision, name="history_entry.decision"))
        object.__setattr__(self, "solution", require_nonblank_str(self.solution, name="history_entry.solution"))
        object.__setattr__(
            self, "regression_test", require_nonblank_str(self.regression_test, name="history_entry.regression_test")
        )
        object.__setattr__(self, "result", require_nonblank_str(self.result, name="history_entry.result"))

    def superseded(self, by_id: str) -> HistoryEntry:
        return HistoryEntry(
            id=self.id,
            sequence=self.sequence,
            improvement_id=self.improvement_id,
            problem=self.problem,
            evidence_ids=self.evidence_ids,
            root_cause_id=self.root_cause_id,
            failed_attempts=self.failed_attempts,
            decision=self.decision,
            solution=self.solution,
            regression_test=self.regression_test,
            result=self.result,
            lesson_id=self.lesson_id,
            superseded_by=require_nonblank_str(by_id, name="superseded_by"),
        )


class HistoryLog:
    """Bounded, insertion-ordered history with deterministic FIFO eviction."""

    def __init__(self, *, max_entries: int) -> None:
        if max_entries < 1:
            raise ValidationError("max_entries must be >= 1")
        self._max_entries = max_entries
        self._entries: dict[str, HistoryEntry] = {}
        self._order: list[str] = []
        self._next_sequence = 0
        self._evicted_count = 0

    @property
    def evicted_count(self) -> int:
        return self._evicted_count

    def add(
        self,
        *,
        id: str,
        improvement_id: str,
        problem: str,
        evidence_ids: tuple[str, ...] = (),
        root_cause_id: str | None = None,
        failed_attempts: tuple[str, ...] = (),
        decision: str,
        solution: str,
        regression_test: str,
        result: str,
        lesson_id: str | None = None,
    ) -> HistoryEntry:
        if id in self._entries:
            raise ValidationError(f"history entry id already exists: {id!r}")
        entry = HistoryEntry(
            id=id,
            sequence=self._next_sequence,
            improvement_id=improvement_id,
            problem=problem,
            evidence_ids=evidence_ids,
            root_cause_id=root_cause_id,
            failed_attempts=failed_attempts,
            decision=decision,
            solution=solution,
            regression_test=regression_test,
            result=result,
            lesson_id=lesson_id,
        )
        self._next_sequence += 1
        self._entries[id] = entry
        self._order.append(id)
        while len(self._order) > self._max_entries:
            oldest_id = self._order.pop(0)
            del self._entries[oldest_id]
            self._evicted_count += 1
        return entry

    def supersede(self, old_id: str, new_id: str) -> None:
        if old_id not in self._entries:
            raise ValidationError(f"unknown history entry id: {old_id!r}")
        if new_id not in self._entries:
            raise ValidationError(f"unknown superseding history entry id: {new_id!r}")
        self._entries[old_id] = self._entries[old_id].superseded(new_id)

    def has(self, id: str) -> bool:
        return id in self._entries

    def get(self, id: str) -> HistoryEntry:
        try:
            return self._entries[id]
        except KeyError:
            raise ValidationError(f"unknown history entry id: {id!r}") from None

    def entries(self, *, limit: int | None = None, newest_first: bool = True) -> tuple[HistoryEntry, ...]:
        ordered_ids = list(reversed(self._order)) if newest_first else list(self._order)
        if limit is not None:
            ordered_ids = ordered_ids[:limit]
        return tuple(self._entries[i] for i in ordered_ids)

    def for_improvement(self, improvement_id: str) -> tuple[HistoryEntry, ...]:
        return tuple(e for e in self.entries(newest_first=False) if e.improvement_id == improvement_id)

    def __len__(self) -> int:
        return len(self._order)
