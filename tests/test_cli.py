from __future__ import annotations

import json
import subprocess
import sys

import pytest

from projectkaizen.cli import (
    EXIT_ATTENTION,
    EXIT_INCOMPLETE,
    EXIT_INVALID_INPUT,
    EXIT_SUCCESS,
    main,
)


def _mkfile(path, content: str = "x") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _clean_project(tmp_path):
    """A project with no analyzer findings, so status/plan/inspect are quiet."""
    _mkfile(tmp_path / "README.md", "# hi\n")
    _mkfile(tmp_path / "pyproject.toml", "[project]\nname='x'\n")
    _mkfile(tmp_path / ".gitignore", "dist/\n")
    _mkfile(tmp_path / "CONTRIBUTING.md", "# contributing\n")
    _mkfile(tmp_path / "AGENTS.md", "# agents\n")
    _mkfile(tmp_path / "src" / "mymod.py", "def f():\n    return 1\n")
    _mkfile(tmp_path / "tests" / "test_mymod.py", "def test_f():\n    assert f() == 1\n")
    return tmp_path


def test_version_flag(capsys):
    with pytest.raises(SystemExit) as exc_info:
        main(["--version"])
    assert exc_info.value.code == 0
    out = capsys.readouterr().out
    assert "projectkaizen" in out


def test_help_flag(capsys):
    with pytest.raises(SystemExit) as exc_info:
        main(["--help"])
    assert exc_info.value.code == 0
    out = capsys.readouterr().out
    assert "inspect" in out


def test_inspect_findings_on_dirty_project_exits_attention(tmp_path, capsys):
    _mkfile(tmp_path / "a.py", "x = 1\n")
    rc = main(["inspect", str(tmp_path)])
    assert rc == EXIT_ATTENTION
    out = capsys.readouterr().out
    assert "findings detected" in out


def test_inspect_clean_project_exits_success(tmp_path, capsys):
    _clean_project(tmp_path)
    rc = main(["inspect", str(tmp_path)])
    assert rc == EXIT_SUCCESS


def test_inspect_json_is_pure_json_on_stdout(tmp_path, capsys):
    _mkfile(tmp_path / "a.py", "x = 1\n")
    main(["--json", "inspect", str(tmp_path)])
    out = capsys.readouterr().out
    payload = json.loads(out)  # raises if anything but pure JSON was printed
    assert payload["command"] == "inspect"
    assert "findings_shown" in payload


def test_inspect_json_is_deterministic(tmp_path, capsys):
    _mkfile(tmp_path / "a.py", "x = 1\n")
    main(["--json", "inspect", str(tmp_path)])
    out1 = capsys.readouterr().out
    main(["--json", "inspect", str(tmp_path)])
    out2 = capsys.readouterr().out
    assert out1 == out2


def test_inspect_persist_writes_agentops_file(tmp_path):
    _mkfile(tmp_path / "a.py", "x = 1\n")
    main(["inspect", str(tmp_path), "--persist"])
    persisted = tmp_path / ".agentops" / "kaizen" / "last_inspect.json"
    assert persisted.exists()
    data = json.loads(persisted.read_text(encoding="utf-8"))
    assert data["kind"] == "inspect_result"


def test_plan_shows_only_actionable_findings(tmp_path, capsys):
    _mkfile(tmp_path / "a.py", "x = 1\n")
    rc = main(["plan", str(tmp_path)])
    out = capsys.readouterr().out
    assert rc in (EXIT_SUCCESS, EXIT_ATTENTION)
    assert "improvements" in out


def test_status_clean_project_is_stable(tmp_path, capsys):
    _clean_project(tmp_path)
    rc = main(["status", str(tmp_path)])
    out = capsys.readouterr().out
    assert rc == EXIT_SUCCESS
    assert "kaizen stable: True" in out


def test_baseline_requires_at_least_one_metric(tmp_path, capsys):
    rc = main(["baseline", str(tmp_path)])
    assert rc == EXIT_INVALID_INPUT


def test_baseline_rejects_malformed_metric(tmp_path, capsys):
    rc = main(["baseline", str(tmp_path), "--metric", "not-a-kv-pair"])
    assert rc == EXIT_INVALID_INPUT


def test_baseline_rejects_non_numeric_value(tmp_path, capsys):
    rc = main(["baseline", str(tmp_path), "--metric", "x=abc"])
    assert rc == EXIT_INVALID_INPUT


def test_baseline_writes_persisted_file(tmp_path):
    rc = main(["baseline", str(tmp_path), "--id", "b1", "--metric", "latency_ms=100"])
    assert rc == EXIT_SUCCESS
    persisted = tmp_path / ".agentops" / "kaizen" / "baseline.json"
    assert persisted.exists()


def test_compare_accept_and_reject(tmp_path, capsys):
    baseline = tmp_path / "baseline.json"
    candidate_good = tmp_path / "candidate_good.json"
    candidate_bad = tmp_path / "candidate_bad.json"
    baseline.write_text(
        json.dumps({"id": "b1", "metrics": {"latency_ms": 100.0}, "higher_is_better": {"latency_ms": False}}),
        encoding="utf-8",
    )
    candidate_good.write_text(json.dumps({"id": "c1", "metrics": {"latency_ms": 40.0}}), encoding="utf-8")
    candidate_bad.write_text(json.dumps({"id": "c2", "metrics": {"latency_ms": 200.0}}), encoding="utf-8")

    rc_accept = main(["compare", str(baseline), str(candidate_good)])
    assert rc_accept == EXIT_SUCCESS
    out = capsys.readouterr().out
    assert "verdict: accept" in out

    rc_reject = main(["compare", str(baseline), str(candidate_bad)])
    assert rc_reject == EXIT_ATTENTION
    out = capsys.readouterr().out
    assert "verdict: reject" in out


def test_compare_json_pure(tmp_path, capsys):
    baseline = tmp_path / "baseline.json"
    candidate = tmp_path / "candidate.json"
    baseline.write_text(json.dumps({"id": "b1", "metrics": {"latency_ms": 100.0}}), encoding="utf-8")
    candidate.write_text(json.dumps({"id": "c1", "metrics": {"latency_ms": 100.0}}), encoding="utf-8")
    main(["--json", "compare", str(baseline), str(candidate)])
    out = capsys.readouterr().out
    payload = json.loads(out)
    assert payload["verdict"] == "inconclusive"


def test_compare_missing_file_is_invalid_input(tmp_path, capsys):
    rc = main(["compare", str(tmp_path / "nope1.json"), str(tmp_path / "nope2.json")])
    assert rc == EXIT_INVALID_INPUT


def test_compare_record_identical_repeat_is_idempotent(tmp_path, capsys):
    baseline = tmp_path / "baseline.json"
    candidate = tmp_path / "candidate.json"
    baseline.write_text(json.dumps({"id": "b1", "metrics": {"latency_ms": 100.0}}), encoding="utf-8")
    candidate.write_text(json.dumps({"id": "c1", "metrics": {"latency_ms": 100.0}}), encoding="utf-8")
    proj = tmp_path / "proj"
    proj.mkdir()

    rc1 = main(["compare", str(baseline), str(candidate), "--record", "--path", str(proj)])
    rc2 = main(["compare", str(baseline), str(candidate), "--record", "--path", str(proj)])
    assert rc1 == rc2 == EXIT_INCOMPLETE

    history_file = proj / ".agentops" / "kaizen" / "history.json"
    data = json.loads(history_file.read_text(encoding="utf-8"))
    assert len(data["data"]["entries"]) == 1


def test_compare_record_distinct_comparisons_with_default_ids_both_kept(tmp_path):
    baseline = tmp_path / "baseline.json"
    candidate_a = tmp_path / "candidate_a.json"
    candidate_b = tmp_path / "candidate_b.json"
    # both candidate files omit "id", so both fall back to the same default
    # candidate id; the two comparisons must still both survive in history.
    baseline.write_text(json.dumps({"metrics": {"latency_ms": 100.0}}), encoding="utf-8")
    candidate_a.write_text(json.dumps({"metrics": {"latency_ms": 100.0}}), encoding="utf-8")
    candidate_b.write_text(json.dumps({"metrics": {"latency_ms": 500.0}}), encoding="utf-8")
    proj = tmp_path / "proj"
    proj.mkdir()

    main(["compare", str(baseline), str(candidate_a), "--record", "--path", str(proj)])
    main(["compare", str(baseline), str(candidate_b), "--record", "--path", str(proj)])

    history_file = proj / ".agentops" / "kaizen" / "history.json"
    data = json.loads(history_file.read_text(encoding="utf-8"))
    assert len(data["data"]["entries"]) == 2


def test_history_no_data_yet(tmp_path, capsys):
    rc = main(["history", str(tmp_path)])
    assert rc == EXIT_SUCCESS
    out = capsys.readouterr().out
    assert "no history" in out


def test_history_json_pure(tmp_path, capsys):
    main(["--json", "history", str(tmp_path)])
    out = capsys.readouterr().out
    payload = json.loads(out)
    assert payload["entries_total"] == 0


def test_validate_config_valid(tmp_path, capsys):
    cfg = tmp_path / "cfg.json"
    cfg.write_text(json.dumps({"max_attempts_per_improvement": 5}), encoding="utf-8")
    rc = main(["validate", str(cfg)])
    assert rc == EXIT_SUCCESS


def test_validate_config_invalid(tmp_path, capsys):
    cfg = tmp_path / "cfg.json"
    cfg.write_text(json.dumps({"unknown_key": 1}), encoding="utf-8")
    rc = main(["validate", str(cfg)])
    assert rc == EXIT_INVALID_INPUT


def test_validate_persisted_artifact(tmp_path, capsys):
    from projectkaizen.persistence import write_json_document

    target = tmp_path / "artifact.json"
    write_json_document(target, root=tmp_path, kind="baseline", schema_version=1, payload={"x": 1})
    rc = main(["validate", str(target)])
    assert rc == EXIT_SUCCESS
    out = capsys.readouterr().out
    assert "baseline" in out


def test_validate_missing_file(tmp_path, capsys):
    rc = main(["validate", str(tmp_path / "nope.json")])
    assert rc == EXIT_INVALID_INPUT


def test_validate_invalid_json(tmp_path, capsys):
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    rc = main(["validate", str(bad)])
    assert rc == EXIT_INVALID_INPUT


def test_custom_config_path_used(tmp_path, capsys):
    cfg = tmp_path / "cfg.json"
    cfg.write_text(json.dumps({"max_attempts_per_improvement": 9}), encoding="utf-8")
    proj = tmp_path / "proj"
    proj.mkdir()
    rc = main(["--config", str(cfg), "status", str(proj)])
    assert rc in (EXIT_SUCCESS, EXIT_ATTENTION, EXIT_INCOMPLETE)


def test_invalid_config_path_exits_invalid_input(tmp_path, capsys):
    rc = main(["--config", str(tmp_path / "nope.json"), "status", str(tmp_path)])
    assert rc == EXIT_INVALID_INPUT


def test_full_flag_shows_more_than_concise(tmp_path, capsys):
    for i in range(10):
        _mkfile(tmp_path / f"m{i}.py", f"x{i} = 1\n")
    main(["inspect", str(tmp_path)])
    concise_out = capsys.readouterr().out
    main(["--full", "inspect", str(tmp_path)])
    full_out = capsys.readouterr().out
    assert len(full_out) >= len(concise_out)


# --- Real subprocess end-to-end (the installed console script) -------------


def test_cli_entrypoint_subprocess_help():
    result = subprocess.run(  # noqa: S603
        [sys.executable, "-m", "projectkaizen.cli", "--help"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert "inspect" in result.stdout


def test_cli_entrypoint_subprocess_json_purity(tmp_path):
    _mkfile(tmp_path / "a.py", "x = 1\n")
    result = subprocess.run(  # noqa: S603
        [sys.executable, "-m", "projectkaizen.cli", "--json", "inspect", str(tmp_path)],
        capture_output=True,
        text=True,
        check=False,
    )
    json.loads(result.stdout)  # raises if stdout has anything but pure JSON
