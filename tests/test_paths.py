from __future__ import annotations

import os
import subprocess
import sys

import pytest

from projectkaizen.exceptions import PathEscapeError, ValidationError
from projectkaizen.paths import (
    assert_existing_ancestors_contained,
    is_reparse,
    is_special_file,
    safe_filename,
    safe_id,
    validate_contained,
)


def test_validate_contained_inside_root(tmp_path):
    inside = tmp_path / "sub" / "file.txt"
    inside.parent.mkdir()
    inside.write_text("x")
    validate_contained(inside, tmp_path)


def test_validate_contained_outside_root_raises(tmp_path):
    outside = tmp_path.parent / "outside_marker_dir_for_test"
    with pytest.raises(PathEscapeError):
        validate_contained(outside, tmp_path)


def test_assert_existing_ancestors_contained_walks_up_to_first_existing(tmp_path):
    # target does not exist yet, but its parent (tmp_path) does and is the root
    target = tmp_path / "does" / "not" / "exist.txt"
    assert_existing_ancestors_contained(target, tmp_path)


def test_assert_existing_ancestors_contained_rejects_escape(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    target = tmp_path / "escape" / "x.txt"
    with pytest.raises(PathEscapeError):
        assert_existing_ancestors_contained(target, root)


def test_safe_id_accepts_and_rejects():
    assert safe_id("abc-123_.x") == "abc-123_.x"
    with pytest.raises(ValidationError):
        safe_id("")
    with pytest.raises(ValidationError):
        safe_id("../etc/passwd")
    with pytest.raises(ValidationError):
        safe_id("a/b")
    with pytest.raises(ValidationError):
        safe_id("a\\b")
    with pytest.raises(ValidationError):
        safe_id("a:b")
    with pytest.raises(ValidationError):
        safe_id("has spaces")


def test_safe_filename():
    assert safe_filename("report.json") == "report.json"
    with pytest.raises(ValidationError):
        safe_filename("../escape.json")
    with pytest.raises(ValidationError):
        safe_filename(".")
    with pytest.raises(ValidationError):
        safe_filename("")
    with pytest.raises(ValidationError):
        safe_filename("dir/file.json")


def test_is_reparse_false_for_regular_file(tmp_path):
    f = tmp_path / "regular.txt"
    f.write_text("x")
    assert is_reparse(f) is False


def test_is_special_file_false_for_regular_file(tmp_path):
    f = tmp_path / "regular.txt"
    f.write_text("x")
    assert is_special_file(f) is False


def test_is_special_file_missing_path_returns_false(tmp_path):
    assert is_special_file(tmp_path / "nope.txt") is False


def _make_windows_junction(link: os.PathLike[str], target: os.PathLike[str]) -> bool:
    result = subprocess.run(  # noqa: S603
        ["cmd", "/c", "mklink", "/J", str(link), str(target)],
        capture_output=True,
        check=False,
        shell=False,
    )
    return result.returncode == 0


@pytest.mark.skipif(sys.platform != "win32", reason="junctions are a Windows-only concept")
def test_windows_junction_detected_as_reparse_and_not_followed(tmp_path):
    real_target = tmp_path / "real_target"
    real_target.mkdir()
    (real_target / "secret.txt").write_text("secret")

    root = tmp_path / "root"
    root.mkdir()
    junction = root / "escape_junction"

    created = _make_windows_junction(junction, real_target)
    if not created:
        pytest.skip("mklink /J failed in this environment")

    assert is_reparse(junction) is True

    # containment: the junction itself resolves outside root once followed
    with pytest.raises(PathEscapeError):
        validate_contained(junction / "secret.txt", root)
