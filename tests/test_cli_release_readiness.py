from __future__ import annotations

import json
import subprocess

import pytest

from projectkaizen.cli import EXIT_ATTENTION, EXIT_INCOMPLETE, EXIT_SUCCESS, main

_GIT_AVAILABLE = subprocess.run(["git", "--version"], capture_output=True).returncode == 0  # noqa: S603, S607
pytestmark = pytest.mark.skipif(not _GIT_AVAILABLE, reason="git not available")


def _git(*args: str, cwd: str) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)  # noqa: S603, S607


def _init_repo(tmp_path) -> str:
    root = str(tmp_path)
    _git("init", "-q", cwd=root)
    _git("config", "user.email", "test@example.com", cwd=root)
    _git("config", "user.name", "Test", cwd=root)
    return root


def test_release_readiness_no_baseline(tmp_path, capsys):
    root = _init_repo(tmp_path)
    rc = main(["release-readiness", root])
    assert rc == EXIT_INCOMPLETE
    out = capsys.readouterr().out
    assert "confirm" in out.lower()


def test_release_readiness_json_pure(tmp_path, capsys):
    root = _init_repo(tmp_path)
    main(["--json", "release-readiness", root])
    out = capsys.readouterr().out
    payload = json.loads(out)
    assert payload["command"] == "release-readiness"
    assert payload["outcome"] == "needs_confirmation"


def test_release_readiness_no_blocker_for_identical_refs(tmp_path, capsys):
    root = _init_repo(tmp_path)
    (tmp_path / "a.txt").write_text("x", encoding="utf-8")
    _git("add", "-A", cwd=root)
    _git("commit", "-q", "-m", "first", cwd=root)
    rc = main(["release-readiness", root, "--base", "HEAD", "--target", "HEAD"])
    assert rc == EXIT_SUCCESS
    out = capsys.readouterr().out
    assert "No blocking issues were found" in out


def test_release_readiness_blocked_exit_code(tmp_path, capsys):
    root = _init_repo(tmp_path)
    cli_dir = tmp_path / "src" / "projectkaizen"
    cli_dir.mkdir(parents=True)
    (cli_dir / "cli.py").write_text(
        'subparsers.add_parser("inspect")\nsubparsers.add_parser("plan")\n', encoding="utf-8"
    )
    _git("add", "-A", cwd=root)
    _git("commit", "-q", "-m", "first", cwd=root)
    base_sha = subprocess.run(  # noqa: S603, S607
        ["git", "-C", root, "rev-parse", "HEAD"], capture_output=True, text=True, check=True
    ).stdout.strip()
    (cli_dir / "cli.py").write_text('subparsers.add_parser("inspect")\n', encoding="utf-8")
    _git("add", "-A", cwd=root)
    _git("commit", "-q", "-m", "remove plan", cwd=root)

    rc = main(["release-readiness", root, "--base", base_sha, "--target", "HEAD"])
    assert rc == EXIT_ATTENTION
    out = capsys.readouterr().out
    assert "must fix" in out


def test_release_readiness_full_shows_technical_detail(tmp_path, capsys):
    root = _init_repo(tmp_path)
    main(["release-readiness", root, "--full"])
    out = capsys.readouterr().out
    assert "technical outcome:" in out
