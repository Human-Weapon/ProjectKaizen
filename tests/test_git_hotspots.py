from __future__ import annotations

import subprocess

import pytest

from projectkaizen.analyzers.git_hotspots import analyze_git_hotspots
from projectkaizen.models import AnalysisStatus


def _git(*args: str, cwd: str) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)  # noqa: S603, S607


def _init_repo_with_history(tmp_path) -> str:
    root = str(tmp_path)
    _git("init", "-q", cwd=root)
    _git("config", "user.email", "test@example.com", cwd=root)
    _git("config", "user.name", "Test", cwd=root)

    (tmp_path / "hot.py").write_text("v1", encoding="utf-8")
    (tmp_path / "cold.py").write_text("v1", encoding="utf-8")
    _git("add", "-A", cwd=root)
    _git("commit", "-q", "-m", "initial", cwd=root)

    for i in range(3):
        (tmp_path / "hot.py").write_text(f"v{i + 2}", encoding="utf-8")
        _git("add", "-A", cwd=root)
        _git("commit", "-q", "-m", f"touch hot {i}", cwd=root)
    return root


_GIT_AVAILABLE = subprocess.run(["git", "--version"], capture_output=True).returncode == 0  # noqa: S603, S607


@pytest.mark.skipif(not _GIT_AVAILABLE, reason="git not available")
def test_hotspot_ranks_frequently_changed_file_first(tmp_path):
    root = _init_repo_with_history(tmp_path)
    result = analyze_git_hotspots(root)
    assert result.status == AnalysisStatus.COMPLETE
    assert result.commits_analyzed == 4
    assert result.hotspots[0].relative_path == "hot.py"
    assert result.hotspots[0].commit_count == 4
    cold = next(h for h in result.hotspots if h.relative_path == "cold.py")
    assert cold.commit_count == 1
    assert result.hotspots[0].score > cold.score


def test_non_git_directory_reports_incomplete_honestly(tmp_path):
    result = analyze_git_hotspots(str(tmp_path))
    assert result.status == AnalysisStatus.ANALYSIS_INCOMPLETE
    assert result.hotspots == ()
    assert any("not a git repository" in r for r in result.incomplete_reasons)


def test_missing_git_executable_reports_failed(tmp_path, monkeypatch):
    import projectkaizen.analyzers.git_hotspots as module

    def _fake_run_bounded(*args, **kwargs):
        from projectkaizen.exceptions import ValidationError

        raise ValidationError("cannot start verification command: [WinError 2]")

    monkeypatch.setattr(module, "run_bounded", _fake_run_bounded)
    result = module.analyze_git_hotspots(str(tmp_path))
    assert result.status == AnalysisStatus.FAILED
    assert "git executable not found" in result.incomplete_reasons


def test_empty_repo_no_commits_yet(tmp_path):
    root = str(tmp_path)
    _git("init", "-q", cwd=root)
    result = analyze_git_hotspots(root)
    assert result.status == AnalysisStatus.COMPLETE
    assert result.commits_analyzed == 0
    assert result.hotspots == ()


def test_hotspot_result_deterministic_across_repeated_calls(tmp_path):
    root = _init_repo_with_history(tmp_path)
    r1 = analyze_git_hotspots(root)
    r2 = analyze_git_hotspots(root)
    assert r1.hotspots == r2.hotspots


def test_generated_and_vendor_paths_excluded_from_ranking(tmp_path):
    root = str(tmp_path)
    _git("init", "-q", cwd=root)
    _git("config", "user.email", "test@example.com", cwd=root)
    _git("config", "user.name", "Test", cwd=root)

    (tmp_path / "real_source.py").write_text("v1", encoding="utf-8")
    (tmp_path / "dist").mkdir()
    (tmp_path / "dist" / "bundle.js").write_text("v1", encoding="utf-8")
    _git("add", "-A", cwd=root)
    _git("commit", "-q", "-m", "initial", cwd=root)

    # the generated file is regenerated on every commit (high churn from a
    # machine); the real source file changes once more.
    for i in range(5):
        (tmp_path / "dist" / "bundle.js").write_text(f"generated {i}", encoding="utf-8")
        _git("add", "-A", cwd=root)
        _git("commit", "-q", "-m", f"rebuild {i}", cwd=root)
    (tmp_path / "real_source.py").write_text("v2", encoding="utf-8")
    _git("add", "-A", cwd=root)
    _git("commit", "-q", "-m", "real change", cwd=root)

    result = analyze_git_hotspots(root)
    paths = [h.relative_path for h in result.hotspots]
    assert "dist/bundle.js" not in paths
    assert "real_source.py" in paths


def test_max_commits_limit_marks_incomplete(tmp_path):
    root = _init_repo_with_history(tmp_path)
    result = analyze_git_hotspots(root, max_commits=2)
    assert result.status == AnalysisStatus.ANALYSIS_INCOMPLETE
    assert any("history limited" in r for r in result.incomplete_reasons)
