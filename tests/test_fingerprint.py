from __future__ import annotations

import pytest

from projectkaizen.exceptions import ValidationError
from projectkaizen.fingerprint import deterministic_id, fingerprint_bytes, fingerprint_file, fingerprint_text


def test_fingerprint_bytes_deterministic():
    assert fingerprint_bytes(b"hello") == fingerprint_bytes(b"hello")


def test_fingerprint_bytes_differs_for_different_input():
    assert fingerprint_bytes(b"hello") != fingerprint_bytes(b"world")


def test_fingerprint_text_matches_bytes_encoding():
    assert fingerprint_text("hello") == fingerprint_bytes(b"hello")


def test_fingerprint_file_deterministic(tmp_path):
    f = tmp_path / "f.txt"
    f.write_text("hello world", encoding="utf-8")
    assert fingerprint_file(f, max_bytes=1000) == fingerprint_file(f, max_bytes=1000)


def test_fingerprint_file_truncation_changes_fingerprint(tmp_path):
    f = tmp_path / "f.txt"
    f.write_text("hello world", encoding="utf-8")
    full = fingerprint_file(f, max_bytes=1000)
    truncated = fingerprint_file(f, max_bytes=5)
    assert full != truncated


def test_fingerprint_file_rejects_negative_max_bytes(tmp_path):
    f = tmp_path / "f.txt"
    f.write_text("x", encoding="utf-8")
    with pytest.raises(ValidationError):
        fingerprint_file(f, max_bytes=-1)


def test_deterministic_id_stable_and_namespaced():
    a = deterministic_id("finding", "x", "y")
    b = deterministic_id("finding", "x", "y")
    c = deterministic_id("other", "x", "y")
    assert a == b
    assert a != c
    assert a.startswith("finding_")


def test_deterministic_id_rejects_empty_namespace():
    with pytest.raises(ValidationError):
        deterministic_id("", "x")


def test_deterministic_id_sensitive_to_part_boundaries():
    # "ab","c" vs "a","bc" must not collide despite naive concatenation
    a = deterministic_id("ns", "ab", "c")
    b = deterministic_id("ns", "a", "bc")
    assert a != b
