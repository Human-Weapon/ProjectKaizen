"""Regression tests from the self-adversarial review pass (spec section 59).

Each test here documents a specific attack/edge case that was deliberately
tried against the CLI and either confirmed safe or fixed.
"""

from __future__ import annotations

import io
import json
from contextlib import redirect_stdout

import pytest
from conftest import make_finding

from projectkaizen.cli import EXIT_CORRUPT_STATE, _reject_duplicate_finding_ids, main
from projectkaizen.exceptions import ProjectKaizenError


def _mkfile(path, content: str = "x") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_corrupt_history_json_fails_closed_not_silently_empty(tmp_path, capsys):
    agentops = tmp_path / ".agentops" / "kaizen"
    agentops.mkdir(parents=True)
    (agentops / "history.json").write_text("{not json", encoding="utf-8")

    rc = main(["history", str(tmp_path)])
    assert rc == EXIT_CORRUPT_STATE
    err = capsys.readouterr().err
    assert "not valid JSON" in err
    # the corrupt file must be quarantined, not silently repaired or deleted
    assert (agentops / "history.json.corrupt").exists()


def test_corrupt_history_json_does_not_report_zero_entries(tmp_path, capsys):
    """A corrupt history file must never be indistinguishable from 'no history yet'."""
    agentops = tmp_path / ".agentops" / "kaizen"
    agentops.mkdir(parents=True)
    (agentops / "history.json").write_text("garbage", encoding="utf-8")

    rc = main(["--json", "history", str(tmp_path)])
    assert rc == EXIT_CORRUPT_STATE
    out = capsys.readouterr().out
    assert out == ""  # nothing fake printed to stdout on failure


def test_huge_finding_set_default_output_stays_bounded(tmp_path, capsys):
    for i in range(150):
        _mkfile(tmp_path / f"mod_{i}.py", f"# TODO fix {i}\nx{i} = 1\n")
    rc = main(["inspect", str(tmp_path)])
    out = capsys.readouterr().out
    assert rc == 1
    # concise default must summarize, never dump 150+ raw findings
    assert out.count("[") < 50


def test_status_and_plan_agree_on_finding_set(tmp_path):
    """Concise and full views must derive from the same underlying facts."""
    _mkfile(tmp_path / "a.py", "x = 1\n")
    buf1, buf2 = io.StringIO(), io.StringIO()
    with redirect_stdout(buf1):
        main(["--json", "inspect", str(tmp_path)])
    with redirect_stdout(buf2):
        main(["inspect", str(tmp_path), "--json", "--full"])
    concise = json.loads(buf1.getvalue())
    full = json.loads(buf2.getvalue())
    assert concise["findings_total"] == full["findings_total"]


def test_duplicate_finding_ids_fail_loudly_not_silently_dropped():
    """Two findings sharing an id would silently overwrite one another in
    any {f.id: f for f in findings} dict — this must raise instead."""
    a = make_finding("dup")
    b = make_finding("dup")
    with pytest.raises(ProjectKaizenError, match="duplicate finding id"):
        _reject_duplicate_finding_ids((a, b))


def test_distinct_finding_ids_pass_through():
    a = make_finding("f1")
    b = make_finding("f2")
    _reject_duplicate_finding_ids((a, b))  # must not raise


def test_global_flags_work_before_and_after_subcommand(tmp_path, capsys):
    """`--json inspect .` and `inspect . --json` must behave identically.

    argparse subparsers silently clobber a top-level flag with the
    subparser's own default unless the subparser's copy suppresses its
    default — this regression-tests that fix.
    """
    _mkfile(tmp_path / "a.py", "x = 1\n")

    main(["--json", "inspect", str(tmp_path)])
    before = capsys.readouterr().out
    main(["inspect", str(tmp_path), "--json"])
    after = capsys.readouterr().out

    assert before == after
    json.loads(before)  # both must be pure, parseable JSON
