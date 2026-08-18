"""Release tag resolution, in pure Python (no bash dependency).

ADAPTED from the tag-resolution step of OpenAI Agents Python's
final-release-review skill (`find_latest_release_tag.sh`) — see
docs/oss-reuse-manifest.md for the exact provenance record and file
comparison. Adapted, not ported verbatim: the original shells out to
`git fetch --tags --prune` before resolving (network access) and delegates
version ordering to `git tag --sort=-v:refname`; this version never
fetches (core ProjectKaizen stays offline — fetching remote tags would need
to be explicit and separately authorized) and does its own semantic-version
parsing/sorting in Python rather than relying on git's `-v:refname` sort.
"""

from __future__ import annotations

import re

from ..exceptions import ValidationError
from ..process import run_bounded

_VERSION_TAG_RE = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)(?:[-+].*)?$")


def parse_version_tag(tag: str) -> tuple[int, int, int] | None:
    """Parse a `v1.2.3` / `1.2.3` style tag. Returns None if not version-like."""
    match = _VERSION_TAG_RE.match(tag.strip())
    if not match:
        return None
    return (int(match.group(1)), int(match.group(2)), int(match.group(3)))


def list_tags(project_root: str, *, timeout_seconds: float = 10.0) -> tuple[str, ...]:
    """Local, offline tag listing — never fetches from a remote."""
    try:
        code, out, _err, timed_out, *_ = run_bounded(
            ["git", "-C", project_root, "tag", "--list"],
            cwd=None,
            env=None,
            timeout=timeout_seconds,
            max_stdout_bytes=8 * 1024 * 1024,
            max_stderr_bytes=1024 * 1024,
        )
    except ValidationError:
        return ()
    if timed_out or code != 0:
        return ()
    return tuple(line.strip() for line in out.decode("utf-8", errors="replace").splitlines() if line.strip())


def resolve_latest_tag(project_root: str, *, timeout_seconds: float = 10.0) -> str | None:
    """The highest version-like tag, deterministically. None if the
    repository has no usable version tags at all — this function never
    invents a fallback baseline; that decision belongs to `scope.py`.
    """
    tags = list_tags(project_root, timeout_seconds=timeout_seconds)
    versioned = [(parse_version_tag(t), t) for t in tags]
    versioned = [(v, t) for v, t in versioned if v is not None]
    if not versioned:
        return None
    versioned.sort(key=lambda pair: (pair[0], pair[1]))
    return versioned[-1][1]
