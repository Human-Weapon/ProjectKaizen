"""Best-effort path containment for output roots and inspected trees.

This is defensive filesystem handling, not a security sandbox against a
privileged local attacker. Containment is re-checked immediately before
creating artifacts so a rejected operation leaves zero files outside the
trusted root under the tested symlink/junction swap cases.
"""

from __future__ import annotations

import os
import re
import stat
from pathlib import Path

from .exceptions import PathEscapeError, ValidationError

SAFE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,199}$")


def resolve_canonical(path: str | Path) -> Path:
    return Path(os.path.realpath(str(path)))


def normalize_path_key(path: str | Path) -> str:
    text = os.path.normpath(str(path))
    if os.name == "nt":
        text = os.path.normcase(text)
    return text


def is_relative_to(path: Path, base: Path) -> bool:
    try:
        Path(normalize_path_key(path)).relative_to(Path(normalize_path_key(base)))
        return True
    except ValueError:
        return False


def validate_contained(target: str | Path, base: str | Path) -> Path:
    base_canonical = resolve_canonical(base)
    target_canonical = resolve_canonical(target)
    if not is_relative_to(target_canonical, base_canonical):
        raise PathEscapeError(
            f"Path '{target}' resolves to '{target_canonical}' which is outside the allowed base '{base_canonical}'."
        )
    return target_canonical


def assert_existing_ancestors_contained(target: str | Path, trusted_root: str | Path) -> None:
    root = resolve_canonical(trusted_root)
    current = Path(target)
    while True:
        if current.exists() or current.is_symlink():
            validate_contained(current, root)
            break
        if current.parent == current:
            break
        current = current.parent


def safe_id(value: str, *, name: str = "id") -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"{name} must be a non-blank string")
    text = value.strip()
    if ".." in text or "/" in text or "\\" in text or ":" in text:
        raise ValidationError(f"{name} must not contain path separators or '..': {text!r}")
    if not SAFE_ID_RE.match(text):
        raise ValidationError(f"{name} must match {SAFE_ID_RE.pattern} (got {text!r})")
    return text


def safe_filename(name: str) -> str:
    if name != Path(name).name or ".." in name or "/" in name or "\\" in name:
        raise ValidationError(f"unsafe output name: {name!r}")
    if not name or name in {".", ".."}:
        raise ValidationError(f"unsafe output name: {name!r}")
    return name


def is_reparse(path: str | Path) -> bool:
    """True for symlinks and Windows junctions/reparse points (not followed)."""
    target = Path(path)
    try:
        if target.is_symlink():
            return True
    except OSError:
        return False
    if os.name != "nt":
        return False
    try:
        st = os.lstat(target)
    except OSError:
        return False
    attrs = getattr(st, "st_file_attributes", 0)
    return bool(attrs & stat.FILE_ATTRIBUTE_REPARSE_POINT)


def is_special_file(path: str | Path) -> bool:
    try:
        st = os.lstat(path)
    except OSError:
        return False
    mode = st.st_mode
    return stat.S_ISSOCK(mode) or stat.S_ISCHR(mode) or stat.S_ISBLK(mode) or stat.S_ISFIFO(mode)
