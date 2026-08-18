from __future__ import annotations

import json

import pytest

from projectkaizen.exceptions import CorruptStateError, PathEscapeError, PersistenceError, ValidationError
from projectkaizen.persistence import (
    atomic_write_bytes,
    dump_canonical_json,
    read_json_document,
    write_json_document,
)


def test_dump_canonical_json_sorted_and_deterministic():
    payload = {"b": 2, "a": 1}
    out1 = dump_canonical_json(payload)
    out2 = dump_canonical_json({"a": 1, "b": 2})
    assert out1 == out2
    assert out1.index(b'"a"') < out1.index(b'"b"')


def test_dump_canonical_json_rejects_nan():
    with pytest.raises(ValidationError):
        dump_canonical_json({"x": float("nan")})


def test_write_and_read_roundtrip(tmp_path):
    root = tmp_path
    target = root / "kaizen" / "state.json"
    write_json_document(target, root=root, kind="k", schema_version=1, payload={"x": 1})
    data = read_json_document(target, root=root, expected_kind="k", expected_schema_version=1)
    assert data == {"x": 1}


def test_write_leaves_no_temp_files(tmp_path):
    target = tmp_path / "kaizen" / "state.json"
    write_json_document(target, root=tmp_path, kind="k", schema_version=1, payload={"x": 1})
    leftovers = [p for p in (tmp_path / "kaizen").iterdir() if p.name != "state.json"]
    assert leftovers == []


def test_write_is_atomic_replace_not_partial(tmp_path):
    target = tmp_path / "kaizen" / "state.json"
    write_json_document(target, root=tmp_path, kind="k", schema_version=1, payload={"v": 1})
    write_json_document(target, root=tmp_path, kind="k", schema_version=1, payload={"v": 2})
    data = read_json_document(target, root=tmp_path, expected_kind="k", expected_schema_version=1)
    assert data == {"v": 2}


def test_path_escape_rejected(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    outside = tmp_path / "outside.json"
    with pytest.raises(PathEscapeError):
        write_json_document(outside, root=root, kind="k", schema_version=1, payload={})


def test_reserved_keys_rejected(tmp_path):
    with pytest.raises(PersistenceError):
        write_json_document(tmp_path / "x.json", root=tmp_path, kind="k", schema_version=1, payload={"kind": "sneaky"})


def test_non_dict_payload_rejected(tmp_path):
    with pytest.raises(PersistenceError):
        write_json_document(tmp_path / "x.json", root=tmp_path, kind="k", schema_version=1, payload=[1, 2])


def test_corrupt_json_quarantined_and_raises(tmp_path):
    target = tmp_path / "state.json"
    target.write_text("{not json", encoding="utf-8")
    with pytest.raises(CorruptStateError) as exc_info:
        read_json_document(target, root=tmp_path, expected_kind="k", expected_schema_version=1)
    quarantined = exc_info.value.quarantined_path
    assert quarantined is not None
    from pathlib import Path

    assert Path(quarantined).exists()
    assert not target.exists()


def test_missing_envelope_keys_quarantined(tmp_path):
    target = tmp_path / "state.json"
    target.write_text(json.dumps({"just": "data"}), encoding="utf-8")
    with pytest.raises(CorruptStateError):
        read_json_document(target, root=tmp_path, expected_kind="k", expected_schema_version=1)


def test_wrong_kind_rejected(tmp_path):
    target = tmp_path / "state.json"
    write_json_document(target, root=tmp_path, kind="actual_kind", schema_version=1, payload={})
    with pytest.raises(CorruptStateError):
        read_json_document(target, root=tmp_path, expected_kind="other_kind", expected_schema_version=1)


def test_wrong_schema_version_rejected(tmp_path):
    target = tmp_path / "state.json"
    write_json_document(target, root=tmp_path, kind="k", schema_version=1, payload={})
    with pytest.raises(CorruptStateError):
        read_json_document(target, root=tmp_path, expected_kind="k", expected_schema_version=2)


def test_invalid_utf8_quarantined(tmp_path):
    target = tmp_path / "state.json"
    target.write_bytes(b"\xff\xfe\x00bad")
    with pytest.raises(CorruptStateError):
        read_json_document(target, root=tmp_path, expected_kind="k", expected_schema_version=1)


def test_read_missing_file_raises_file_not_found(tmp_path):
    with pytest.raises(FileNotFoundError):
        read_json_document(tmp_path / "nope.json", root=tmp_path, expected_kind="k", expected_schema_version=1)


def test_corruption_does_not_silently_return_empty_default(tmp_path):
    target = tmp_path / "state.json"
    target.write_text("garbage", encoding="utf-8")
    with pytest.raises(CorruptStateError):
        result = read_json_document(target, root=tmp_path, expected_kind="k", expected_schema_version=1)
        assert result != {}  # unreachable if the exception fires as expected


def test_repeated_quarantine_does_not_overwrite_previous(tmp_path):
    target = tmp_path / "state.json"
    target.write_text("bad1", encoding="utf-8")
    with pytest.raises(CorruptStateError):
        read_json_document(target, root=tmp_path, expected_kind="k", expected_schema_version=1)
    target.write_text("bad2", encoding="utf-8")
    with pytest.raises(CorruptStateError):
        read_json_document(target, root=tmp_path, expected_kind="k", expected_schema_version=1)
    assert (tmp_path / "state.json.corrupt").exists()
    assert (tmp_path / "state.json.corrupt.1").exists()


def test_atomic_write_bytes_creates_parent_dirs(tmp_path):
    target = tmp_path / "a" / "b" / "c.json"
    atomic_write_bytes(target, root=tmp_path, data=b"hello")
    assert target.read_bytes() == b"hello"
