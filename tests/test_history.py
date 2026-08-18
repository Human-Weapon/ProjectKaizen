from __future__ import annotations

import pytest

from projectkaizen.exceptions import ValidationError
from projectkaizen.history import HistoryLog


def _add(log: HistoryLog, id: str, improvement_id: str = "imp1") -> None:
    log.add(
        id=id,
        improvement_id=improvement_id,
        problem="p",
        decision="accept",
        solution="s",
        regression_test="rt",
        result="r",
    )


def test_add_and_get():
    log = HistoryLog(max_entries=10)
    _add(log, "h1")
    entry = log.get("h1")
    assert entry.id == "h1"
    assert entry.sequence == 0


def test_duplicate_id_rejected():
    log = HistoryLog(max_entries=10)
    _add(log, "h1")
    with pytest.raises(ValidationError):
        _add(log, "h1")


def test_get_unknown_raises():
    log = HistoryLog(max_entries=10)
    with pytest.raises(ValidationError):
        log.get("nope")


def test_bounded_fifo_eviction():
    log = HistoryLog(max_entries=2)
    _add(log, "h1")
    _add(log, "h2")
    _add(log, "h3")
    assert len(log) == 2
    assert log.evicted_count == 1
    with pytest.raises(ValidationError):
        log.get("h1")
    assert log.get("h3").id == "h3"


def test_entries_newest_first_by_default():
    log = HistoryLog(max_entries=10)
    _add(log, "h1")
    _add(log, "h2")
    assert [e.id for e in log.entries()] == ["h2", "h1"]
    assert [e.id for e in log.entries(newest_first=False)] == ["h1", "h2"]


def test_entries_limit():
    log = HistoryLog(max_entries=10)
    for i in range(5):
        _add(log, f"h{i}")
    assert len(log.entries(limit=2)) == 2


def test_for_improvement_filters():
    log = HistoryLog(max_entries=10)
    _add(log, "h1", improvement_id="a")
    _add(log, "h2", improvement_id="b")
    _add(log, "h3", improvement_id="a")
    assert [e.id for e in log.for_improvement("a")] == ["h1", "h3"]


def test_supersede_marks_entry_and_preserves_id():
    log = HistoryLog(max_entries=10)
    _add(log, "h1")
    _add(log, "h2")
    log.supersede("h1", "h2")
    entry = log.get("h1")
    assert entry.superseded_by == "h2"
    assert entry.id == "h1"


def test_supersede_unknown_ids_raise():
    log = HistoryLog(max_entries=10)
    _add(log, "h1")
    with pytest.raises(ValidationError):
        log.supersede("nope", "h1")
    with pytest.raises(ValidationError):
        log.supersede("h1", "nope")


def test_max_entries_must_be_positive():
    with pytest.raises(ValidationError):
        HistoryLog(max_entries=0)


def test_history_entry_requires_nonblank_fields():
    log = HistoryLog(max_entries=10)
    with pytest.raises(ValidationError):
        log.add(id="h1", improvement_id="i1", problem="", decision="d", solution="s", regression_test="rt", result="r")
