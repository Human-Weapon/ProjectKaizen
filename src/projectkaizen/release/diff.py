"""Base-vs-target file diff and change-category classification.

A changed file is discovery evidence, not a finding — `classify_change`
tags *what kind* of change it might be so `checklist.py`/`readiness.py`
can decide whether that's actually risky; this module makes no risk
judgment itself.
"""

from __future__ import annotations

from ..exceptions import ValidationError
from ..process import run_bounded
from .models import ChangeCategory, ChangedFile, ChangeType

_STATUS_MAP = {"A": ChangeType.ADDED, "M": ChangeType.MODIFIED, "D": ChangeType.DELETED}


def _classify_path(path: str) -> tuple[ChangeCategory, ...]:
    categories: list[ChangeCategory] = []
    lower = path.lower()

    if path in ("pyproject.toml", "setup.py", "setup.cfg"):
        categories.append(ChangeCategory.PACKAGE_METADATA)
        categories.append(ChangeCategory.DEPENDENCIES)
        categories.append(ChangeCategory.PYTHON_SUPPORT)
    if path.endswith("__init__.py"):
        categories.append(ChangeCategory.PUBLIC_API)
        categories.append(ChangeCategory.COMPATIBILITY)
    if "cli.py" in lower:
        categories.append(ChangeCategory.CLI_CONTRACT)
    if "config" in lower:
        categories.append(ChangeCategory.CONFIG)
        categories.append(ChangeCategory.ENV_VARS)
    if "persistence" in lower or "schema" in lower:
        categories.append(ChangeCategory.PERSISTED_SCHEMA)
    if "exceptions.py" in lower:
        categories.append(ChangeCategory.ERROR_BEHAVIOR)
    if "process.py" in lower or "walker.py" in lower:
        categories.append(ChangeCategory.CONCURRENCY_LIFECYCLE)
    if "workflows" in lower or path == ".github/workflows":
        categories.append(ChangeCategory.ARTIFACTS)
    if "migration" in lower:
        categories.append(ChangeCategory.MIGRATIONS)

    if not categories:
        categories.append(ChangeCategory.OTHER)
    return tuple(dict.fromkeys(categories))


def classify_change(path: str) -> tuple[ChangeCategory, ...]:
    return _classify_path(path)


def compute_changed_files(
    project_root: str, *, base_sha: str, target_sha: str, timeout_seconds: float = 15.0
) -> tuple[ChangedFile, ...]:
    try:
        code, out, _err, timed_out, *_ = run_bounded(
            ["git", "-C", project_root, "diff", "--name-status", "--find-renames", base_sha, target_sha],
            cwd=None,
            env=None,
            timeout=timeout_seconds,
            max_stdout_bytes=32 * 1024 * 1024,
            max_stderr_bytes=1024 * 1024,
        )
    except ValidationError:
        return ()
    if timed_out or code != 0:
        return ()

    changed: list[ChangedFile] = []
    for line in out.decode("utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        status = parts[0]
        if status.startswith("R"):
            # rename: status, old path, new path
            path = parts[2] if len(parts) > 2 else parts[-1]
            change_type = ChangeType.RENAMED
        else:
            path = parts[-1]
            change_type = _STATUS_MAP.get(status[:1], ChangeType.MODIFIED)
        changed.append(ChangedFile(path=path, change_type=change_type, categories=classify_change(path)))

    changed.sort(key=lambda c: c.path)
    return tuple(changed)
