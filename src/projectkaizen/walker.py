"""Safe, bounded filesystem walking.

Symlinks and Windows junctions/reparse points are never followed. Depth,
file-count, and byte limits are enforced and any limit that trims the walk
is reported as an explicit incomplete reason — the walker never silently
reports COMPLETE after dropping data.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from .exceptions import ValidationError
from .models import AnalysisStatus
from .paths import is_reparse, is_special_file, resolve_canonical, validate_contained

DEFAULT_IGNORED_DIRS = frozenset(
    {
        ".git",
        "__pycache__",
        ".venv",
        "venv",
        "node_modules",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".tox",
        ".agentops",
    }
)


@dataclass(frozen=True, slots=True)
class WalkedFile:
    relative_path: str
    absolute_path: str
    size_bytes: int


@dataclass(frozen=True, slots=True)
class WalkResult:
    root: str
    files: tuple[WalkedFile, ...]
    status: AnalysisStatus
    incomplete_reasons: tuple[str, ...]
    total_bytes: int
    skipped_reparse_points: tuple[str, ...]
    skipped_special_files: tuple[str, ...]
    skipped_unreadable: tuple[str, ...]


def walk_project(
    root: str | Path,
    *,
    max_files: int,
    max_depth: int,
    max_total_bytes: int,
    ignored_dirs: frozenset[str] = DEFAULT_IGNORED_DIRS,
) -> WalkResult:
    if max_files < 1 or max_depth < 0 or max_total_bytes < 0:
        raise ValidationError("walk_project limits must be non-negative (max_files/max_depth >= 0)")

    root_path = resolve_canonical(root)
    if not root_path.is_dir():
        raise ValidationError(f"walk root is not a directory: {root_path}")

    files: list[WalkedFile] = []
    reparse_points: list[str] = []
    special_files: list[str] = []
    unreadable: list[str] = []
    incomplete_reasons: list[str] = []
    total_bytes = 0
    visited_real_dirs: set[str] = {str(root_path)}

    # (directory, depth) stack; sorted entries at each level for determinism.
    stack: list[tuple[Path, int]] = [(root_path, 0)]
    file_limit_hit = False
    byte_limit_hit = False
    depth_limit_hit = False

    while stack:
        current_dir, depth = stack.pop()
        try:
            entries = sorted(os.scandir(current_dir), key=lambda e: e.name)
        except OSError:
            unreadable.append(str(current_dir))
            continue

        subdirs: list[Path] = []
        for entry in entries:
            entry_path = Path(entry.path)
            try:
                if is_reparse(entry_path):
                    reparse_points.append(str(entry_path))
                    continue
                if is_special_file(entry_path):
                    special_files.append(str(entry_path))
                    continue
                if entry.is_dir(follow_symlinks=False):
                    if entry.name in ignored_dirs:
                        continue
                    subdirs.append(entry_path)
                    continue
                if not entry.is_file(follow_symlinks=False):
                    continue
            except OSError:
                unreadable.append(str(entry_path))
                continue

            if len(files) >= max_files:
                file_limit_hit = True
                continue
            try:
                validate_contained(entry_path, root_path)
                size = entry.stat(follow_symlinks=False).st_size
            except OSError:
                unreadable.append(str(entry_path))
                continue

            if total_bytes + size > max_total_bytes:
                byte_limit_hit = True
                continue

            total_bytes += size
            try:
                relative = entry_path.relative_to(root_path).as_posix()
            except ValueError:
                unreadable.append(str(entry_path))
                continue
            files.append(WalkedFile(relative_path=relative, absolute_path=str(entry_path), size_bytes=size))

        if depth + 1 > max_depth:
            if subdirs:
                depth_limit_hit = True
            continue

        for subdir in sorted(subdirs, reverse=True):
            try:
                real = str(resolve_canonical(subdir))
            except OSError:
                unreadable.append(str(subdir))
                continue
            if real in visited_real_dirs:
                continue
            visited_real_dirs.add(real)
            stack.append((subdir, depth + 1))

    if file_limit_hit:
        incomplete_reasons.append(f"file limit reached (max_files={max_files})")
    if byte_limit_hit:
        incomplete_reasons.append(f"total byte limit reached (max_total_bytes={max_total_bytes})")
    if depth_limit_hit:
        incomplete_reasons.append(f"depth limit reached (max_depth={max_depth})")
    if unreadable:
        incomplete_reasons.append(f"{len(unreadable)} unreadable path(s)")

    status = AnalysisStatus.ANALYSIS_INCOMPLETE if incomplete_reasons else AnalysisStatus.COMPLETE

    files.sort(key=lambda f: f.relative_path)
    return WalkResult(
        root=str(root_path),
        files=tuple(files),
        status=status,
        incomplete_reasons=tuple(incomplete_reasons),
        total_bytes=total_bytes,
        skipped_reparse_points=tuple(sorted(reparse_points)),
        skipped_special_files=tuple(sorted(special_files)),
        skipped_unreadable=tuple(sorted(unreadable)),
    )


@dataclass(frozen=True, slots=True)
class TextReadResult:
    text: str
    truncated: bool
    valid_utf8: bool
    incomplete_sequence: bool


def read_text_bounded(path: str | Path, *, max_bytes: int) -> TextReadResult:
    """Read up to ``max_bytes`` of a file as UTF-8, honestly reporting truncation.

    Distinguishes a genuinely invalid byte sequence from a multi-byte UTF-8
    sequence that was merely cut off by the byte cap (the latter is expected
    and not a data-quality problem).
    """
    if max_bytes < 0:
        raise ValidationError("max_bytes must be >= 0")
    with open(path, "rb") as fh:
        data = fh.read(max_bytes + 1)
    truncated = len(data) > max_bytes
    if truncated:
        data = data[:max_bytes]

    try:
        text = data.decode("utf-8", errors="strict")
        return TextReadResult(text=text, truncated=truncated, valid_utf8=True, incomplete_sequence=False)
    except UnicodeDecodeError as exc:
        tail_len = len(data) - exc.start
        incomplete_sequence = truncated and tail_len <= 4 and exc.end == len(data)
        text = data[: exc.start].decode("utf-8", errors="strict")
        return TextReadResult(text=text, truncated=truncated, valid_utf8=False, incomplete_sequence=incomplete_sequence)
