"""Public-contract comparison between base and target, without checking
out either ref (`git show <sha>:<path>` reads a blob in place — read-only,
no working-tree mutation).

Compares two lightweight, textual signals: the CLI's subcommand set (from
`cli.py`) and `pyproject.toml`'s declared `requires-python`. This is not a
full API diff (that would need real AST/signature comparison across every
public module) — a deliberately small, high-signal slice, honestly scoped.
"""

from __future__ import annotations

import re

from ..exceptions import ValidationError
from ..process import run_bounded
from .models import ChangeCategory, ReleaseFinding, ReleaseFindingStatus

_SUBCOMMAND_RE = re.compile(r'subparsers\.add_parser\(\s*"([\w-]+)"')
_REQUIRES_PYTHON_RE = re.compile(r'requires-python\s*=\s*"([^"]+)"')


def _show(project_root: str, sha: str, path: str, *, timeout_seconds: float) -> str | None:
    try:
        code, out, _err, timed_out, *_ = run_bounded(
            ["git", "-C", project_root, "show", f"{sha}:{path}"],
            cwd=None,
            env=None,
            timeout=timeout_seconds,
            max_stdout_bytes=8 * 1024 * 1024,
            max_stderr_bytes=1024 * 1024,
        )
    except ValidationError:
        return None
    if timed_out or code != 0:
        return None
    return out.decode("utf-8", errors="replace")


def compare_cli_subcommands(
    project_root: str,
    *,
    base_sha: str,
    target_sha: str,
    cli_path: str = "src/projectkaizen/cli.py",
    timeout_seconds: float = 10.0,
) -> ReleaseFinding | None:
    base_text = _show(project_root, base_sha, cli_path, timeout_seconds=timeout_seconds)
    target_text = _show(project_root, target_sha, cli_path, timeout_seconds=timeout_seconds)
    if base_text is None or target_text is None:
        return None

    base_commands = set(_SUBCOMMAND_RE.findall(base_text))
    target_commands = set(_SUBCOMMAND_RE.findall(target_text))
    removed = sorted(base_commands - target_commands)
    added = sorted(target_commands - base_commands)
    if not removed and not added:
        return None

    from ..fingerprint import deterministic_id

    return ReleaseFinding(
        id=deterministic_id("release_finding", "cli_contract", ",".join(removed + added)),
        category=ChangeCategory.CLI_CONTRACT,
        title="CLI subcommand set changed",
        description=(
            f"removed: {removed or 'none'}; added: {added or 'none'}. Removing a subcommand is a compatibility break."
        ),
        status=ReleaseFindingStatus.BLOCKED if removed else ReleaseFindingStatus.NEEDS_CONFIRMATION,
        evidence=(f"base commands: {sorted(base_commands)}", f"target commands: {sorted(target_commands)}"),
        affected_paths=(cli_path,),
    )


def compare_python_support(
    project_root: str,
    *,
    base_sha: str,
    target_sha: str,
    pyproject_path: str = "pyproject.toml",
    timeout_seconds: float = 10.0,
) -> ReleaseFinding | None:
    base_text = _show(project_root, base_sha, pyproject_path, timeout_seconds=timeout_seconds)
    target_text = _show(project_root, target_sha, pyproject_path, timeout_seconds=timeout_seconds)
    if base_text is None or target_text is None:
        return None

    base_match = _REQUIRES_PYTHON_RE.search(base_text)
    target_match = _REQUIRES_PYTHON_RE.search(target_text)
    base_spec = base_match.group(1) if base_match else None
    target_spec = target_match.group(1) if target_match else None
    if base_spec == target_spec:
        return None

    from ..fingerprint import deterministic_id

    return ReleaseFinding(
        id=deterministic_id("release_finding", "python_support", str(base_spec), str(target_spec)),
        category=ChangeCategory.PYTHON_SUPPORT,
        title="declared Python support changed",
        description=f"requires-python changed from {base_spec!r} to {target_spec!r}; confirm CI matrix still matches",
        status=ReleaseFindingStatus.NEEDS_CONFIRMATION,
        evidence=(f"base: {base_spec}", f"target: {target_spec}"),
        affected_paths=(pyproject_path,),
    )


def compare_contracts(
    project_root: str, *, base_sha: str, target_sha: str, timeout_seconds: float = 10.0
) -> tuple[ReleaseFinding, ...]:
    findings = []
    for fn in (compare_cli_subcommands, compare_python_support):
        result = fn(project_root, base_sha=base_sha, target_sha=target_sha, timeout_seconds=timeout_seconds)
        if result is not None:
            findings.append(result)
    return tuple(findings)
