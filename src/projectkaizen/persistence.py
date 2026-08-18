"""Atomic, schema-validated, corruption-rejecting JSON persistence.

Design contract:

* Writes are atomic: content is written to a sibling temp file and moved
  into place with ``os.replace`` (atomic on the same volume on both POSIX
  and Windows). A crash mid-write leaves either the old file or nothing new
  — never a half-written document.
* Every document carries an explicit ``schema_version`` and ``kind``.
  Reading a document with the wrong kind/version, or with syntactically
  invalid JSON, is a hard failure (:class:`CorruptStateError`) — this module
  never silently "repairs" or discards corrupt state and returns an empty
  default in its place. Corrupt files are quarantined (renamed aside) so
  the failure is inspectable, not lost.
* All target paths are validated against a trusted root via
  :mod:`projectkaizen.paths` both before opening the temp file and again
  immediately before the atomic replace. This narrows, but does not
  eliminate, TOCTOU risk from a concurrent hostile filesystem mutation
  between those two checks — see the module docstring in ``paths.py`` and
  the README security section for the honest limitation.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from .exceptions import CorruptStateError, PersistenceError
from .jsonutil import to_jsonable
from .paths import assert_existing_ancestors_contained, validate_contained

SCHEMA_KEY = "schema_version"
KIND_KEY = "kind"


def dump_canonical_json(value: Any, *, name: str = "document") -> bytes:
    """Deterministic, strict JSON bytes: sorted keys, no NaN/Infinity, UTF-8."""
    jsonable = to_jsonable(value, name=name)
    text = json.dumps(jsonable, sort_keys=True, ensure_ascii=False, allow_nan=False, indent=2)
    return (text + "\n").encode("utf-8")


def atomic_write_bytes(target: str | Path, *, root: str | Path, data: bytes) -> Path:
    """Write ``data`` to ``target`` atomically, refusing to write outside ``root``."""
    target_path = Path(target)
    root_path = Path(root)
    assert_existing_ancestors_contained(target_path, root_path)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    validate_contained(target_path.parent, root_path)

    fd, tmp_name = tempfile.mkstemp(prefix=f".{target_path.name}.", suffix=".tmp", dir=str(target_path.parent))
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        # Re-validate immediately before the replace: narrows, does not
        # eliminate, the TOCTOU window against a concurrent hostile actor.
        validate_contained(target_path.parent, root_path)
        os.replace(tmp_path, target_path)
    except BaseException:
        tmp_path.unlink(missing_ok=True)
        raise
    return target_path


def write_json_document(
    target: str | Path,
    *,
    root: str | Path,
    kind: str,
    schema_version: int,
    payload: Any,
) -> Path:
    if not isinstance(payload, dict):
        raise PersistenceError("document payload must be a dict")
    if SCHEMA_KEY in payload or KIND_KEY in payload:
        raise PersistenceError(f"payload must not set reserved keys {SCHEMA_KEY!r}/{KIND_KEY!r}")
    document = {KIND_KEY: kind, SCHEMA_KEY: schema_version, "data": payload}
    data = dump_canonical_json(document, name=f"{kind}.document")
    return atomic_write_bytes(target, root=root, data=data)


def _quarantine(path: Path) -> Path:
    candidate = path.with_name(path.name + ".corrupt")
    index = 1
    while candidate.exists():
        candidate = path.with_name(f"{path.name}.corrupt.{index}")
        index += 1
    try:
        os.replace(path, candidate)
    except OSError:
        return path
    return candidate


def read_json_document(
    target: str | Path,
    *,
    root: str | Path,
    expected_kind: str,
    expected_schema_version: int,
) -> Any:
    """Read and validate a document written by :func:`write_json_document`.

    Raises :class:`CorruptStateError` (never returns a fabricated default)
    when the file is missing valid JSON, has the wrong kind, or an
    unsupported schema version. The offending file is quarantined so the
    caller can inspect it after the fact.
    """
    target_path = Path(target)
    root_path = Path(root)
    validate_contained(target_path, root_path)

    try:
        raw = target_path.read_bytes()
    except FileNotFoundError:
        raise
    except OSError as exc:
        raise PersistenceError(f"cannot read {target_path}: {exc}") from exc

    try:
        text = raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        quarantined = _quarantine(target_path)
        raise CorruptStateError(f"{target_path} is not valid UTF-8: {exc}", quarantined_path=str(quarantined)) from exc

    try:
        document = json.loads(text)
    except json.JSONDecodeError as exc:
        quarantined = _quarantine(target_path)
        raise CorruptStateError(f"{target_path} is not valid JSON: {exc}", quarantined_path=str(quarantined)) from exc

    has_envelope = isinstance(document, dict) and {KIND_KEY, SCHEMA_KEY, "data"} <= set(document)
    if not has_envelope:
        quarantined = _quarantine(target_path)
        raise CorruptStateError(
            f"{target_path} is missing required envelope keys ({KIND_KEY}/{SCHEMA_KEY}/data)",
            quarantined_path=str(quarantined),
        )

    if document[KIND_KEY] != expected_kind:
        quarantined = _quarantine(target_path)
        raise CorruptStateError(
            f"{target_path} has kind {document[KIND_KEY]!r}, expected {expected_kind!r}",
            quarantined_path=str(quarantined),
        )

    if document[SCHEMA_KEY] != expected_schema_version:
        quarantined = _quarantine(target_path)
        raise CorruptStateError(
            f"{target_path} has schema_version {document[SCHEMA_KEY]!r}, expected {expected_schema_version!r}",
            quarantined_path=str(quarantined),
        )

    return document["data"]
