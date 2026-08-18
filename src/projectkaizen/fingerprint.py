"""Deterministic content fingerprints and ids.

Never uses randomness, wall-clock time, or Python's salted ``hash()`` —
every id here is a pure function of its inputs so the same project state
always produces the same ids, sort order, and serialization (spec section
44: determinism).
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from .exceptions import ValidationError


def fingerprint_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def fingerprint_text(text: str) -> str:
    return fingerprint_bytes(text.encode("utf-8"))


def fingerprint_file(path: str | Path, *, max_bytes: int) -> str:
    """Hash of the first ``max_bytes`` bytes, prefixed by whether it was truncated.

    Bounding the read keeps fingerprinting cheap on huge files while staying
    deterministic: the same (bytes read, truncated?) pair always yields the
    same fingerprint.
    """
    if max_bytes < 0:
        raise ValidationError("max_bytes must be >= 0")
    with open(path, "rb") as fh:
        data = fh.read(max_bytes + 1)
    truncated = len(data) > max_bytes
    if truncated:
        data = data[:max_bytes]
    marker = b"T" if truncated else b"F"
    return fingerprint_bytes(marker + data)


def deterministic_id(namespace: str, *parts: str) -> str:
    """A short, stable, content-derived id: ``<namespace>_<16 hex chars>``."""
    if not namespace:
        raise ValidationError("namespace must be non-empty")
    joined = "\x1f".join((namespace, *parts))
    digest = fingerprint_text(joined)
    return f"{namespace}_{digest[:16]}"
