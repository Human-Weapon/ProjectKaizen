from __future__ import annotations

import subprocess
import sys

import pytest

from projectkaizen.exceptions import ValidationError
from projectkaizen.models import AnalysisStatus
from projectkaizen.walker import read_text_bounded, walk_project


def _mkfile(path, content: str = "x") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_basic_walk_lists_files(tmp_path):
    _mkfile(tmp_path / "a.py")
    _mkfile(tmp_path / "sub" / "b.py")
    result = walk_project(tmp_path, max_files=100, max_depth=64, max_total_bytes=1_000_000)
    assert result.status == AnalysisStatus.COMPLETE
    names = {f.relative_path for f in result.files}
    assert names == {"a.py", "sub/b.py"}


def test_ignored_dirs_excluded(tmp_path):
    _mkfile(tmp_path / "a.py")
    _mkfile(tmp_path / ".git" / "config", "x")
    _mkfile(tmp_path / "__pycache__" / "x.pyc", "x")
    result = walk_project(tmp_path, max_files=100, max_depth=64, max_total_bytes=1_000_000)
    names = {f.relative_path for f in result.files}
    assert names == {"a.py"}


def test_file_limit_marks_incomplete(tmp_path):
    for i in range(5):
        _mkfile(tmp_path / f"f{i}.py")
    result = walk_project(tmp_path, max_files=2, max_depth=64, max_total_bytes=1_000_000)
    assert result.status == AnalysisStatus.ANALYSIS_INCOMPLETE
    assert any("file limit" in r for r in result.incomplete_reasons)
    assert len(result.files) == 2


def test_depth_limit_marks_incomplete(tmp_path):
    _mkfile(tmp_path / "a.py")
    _mkfile(tmp_path / "sub" / "b.py")
    result = walk_project(tmp_path, max_files=100, max_depth=0, max_total_bytes=1_000_000)
    assert result.status == AnalysisStatus.ANALYSIS_INCOMPLETE
    assert any("depth limit" in r for r in result.incomplete_reasons)
    assert {f.relative_path for f in result.files} == {"a.py"}


def test_byte_limit_marks_incomplete(tmp_path):
    _mkfile(tmp_path / "a.py", "x" * 1000)
    _mkfile(tmp_path / "b.py", "x" * 1000)
    result = walk_project(tmp_path, max_files=100, max_depth=64, max_total_bytes=1000)
    assert result.status == AnalysisStatus.ANALYSIS_INCOMPLETE
    assert any("byte limit" in r for r in result.incomplete_reasons)


def test_walk_root_must_be_directory(tmp_path):
    f = tmp_path / "file.txt"
    f.write_text("x")
    with pytest.raises(ValidationError):
        walk_project(f, max_files=100, max_depth=64, max_total_bytes=1_000_000)


def test_walk_project_rejects_invalid_limits(tmp_path):
    with pytest.raises(ValidationError):
        walk_project(tmp_path, max_files=0, max_depth=64, max_total_bytes=1_000_000)


def test_files_are_sorted_deterministically(tmp_path):
    _mkfile(tmp_path / "z.py")
    _mkfile(tmp_path / "a.py")
    _mkfile(tmp_path / "m.py")
    result = walk_project(tmp_path, max_files=100, max_depth=64, max_total_bytes=1_000_000)
    paths = [f.relative_path for f in result.files]
    assert paths == sorted(paths)


def _make_windows_junction(link, target) -> bool:
    result = subprocess.run(  # noqa: S603
        ["cmd", "/c", "mklink", "/J", str(link), str(target)], capture_output=True, check=False, shell=False
    )
    return result.returncode == 0


@pytest.mark.skipif(sys.platform != "win32", reason="junctions are a Windows-only concept")
def test_walk_does_not_follow_junction_escape(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    _mkfile(outside / "secret.txt", "secret")

    root = tmp_path / "root"
    root.mkdir()
    _mkfile(root / "a.py")
    junction = root / "escape"
    if not _make_windows_junction(junction, outside):
        pytest.skip("mklink /J failed in this environment")

    result = walk_project(root, max_files=100, max_depth=64, max_total_bytes=1_000_000)
    assert not any("secret" in f.relative_path for f in result.files)
    assert any("escape" in p for p in result.skipped_reparse_points)


def test_read_text_bounded_full_read(tmp_path):
    f = tmp_path / "f.txt"
    f.write_text("hello world", encoding="utf-8")
    result = read_text_bounded(f, max_bytes=1000)
    assert result.text == "hello world"
    assert result.truncated is False
    assert result.valid_utf8 is True


def test_read_text_bounded_truncates(tmp_path):
    f = tmp_path / "f.txt"
    f.write_text("hello world", encoding="utf-8")
    result = read_text_bounded(f, max_bytes=5)
    assert result.text == "hello"
    assert result.truncated is True


def test_read_text_bounded_invalid_utf8_mid_content(tmp_path):
    f = tmp_path / "f.txt"
    f.write_bytes(b"abc\xffdef")
    result = read_text_bounded(f, max_bytes=1000)
    assert result.valid_utf8 is False
    assert result.text == "abc"
    assert result.incomplete_sequence is False


def test_read_text_bounded_cut_multibyte_sequence_flagged_incomplete(tmp_path):
    f = tmp_path / "f.txt"
    # 'e' with acute accent (2-byte UTF-8: 0xC3 0xA9), cut after the first byte
    content = "cafe\xe9".encode()
    f.write_bytes(content)
    result = read_text_bounded(f, max_bytes=len(content) - 1)
    assert result.truncated is True
    assert result.valid_utf8 is False
    assert result.incomplete_sequence is True


def test_read_text_bounded_rejects_negative_max_bytes(tmp_path):
    f = tmp_path / "f.txt"
    f.write_text("x", encoding="utf-8")
    with pytest.raises(ValidationError):
        read_text_bounded(f, max_bytes=-1)


def test_valid_utf8_replacement_char_is_not_flagged_invalid(tmp_path):
    f = tmp_path / "f.txt"
    f.write_text("has a � literal", encoding="utf-8")
    result = read_text_bounded(f, max_bytes=1000)
    assert result.valid_utf8 is True
    assert "�" in result.text
