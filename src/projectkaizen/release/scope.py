"""Resolve the base/target scope for a release-readiness comparison.

Never invents a baseline (spec section 15). If no explicit base is given
and no usable release tag exists, the scope carries `confidence=NO_BASELINE`
and `base=None` — an honest "we don't have anything to diff against,"
not a guess.
"""

from __future__ import annotations

from ..exceptions import ValidationError
from ..process import run_bounded
from .models import ReleaseRef, ReleaseScope, ScopeConfidence
from .tags import resolve_latest_tag


def _rev_parse(project_root: str, ref: str, *, timeout_seconds: float) -> str | None:
    # `^{commit}` forces dereferencing to the actual commit: plain
    # `git rev-parse <ref>` on an *annotated* tag returns the tag object's
    # own SHA, not the commit it points to (a lightweight tag or branch
    # has no such object, so this is a no-op for those). Self-adversarial
    # finding — without this, ReleaseRef.sha silently meant two different
    # kinds of thing depending on tag type.
    try:
        code, out, _err, timed_out, *_ = run_bounded(
            ["git", "-C", project_root, "rev-parse", f"{ref}^{{commit}}"],
            cwd=None,
            env=None,
            timeout=timeout_seconds,
            max_stdout_bytes=1024,
            max_stderr_bytes=1024 * 1024,
        )
    except ValidationError:
        return None
    if timed_out or code != 0:
        return None
    return out.decode("utf-8", errors="replace").strip() or None


def _is_dirty(project_root: str, *, timeout_seconds: float) -> bool:
    try:
        code, out, _err, timed_out, *_ = run_bounded(
            ["git", "-C", project_root, "status", "--porcelain"],
            cwd=None,
            env=None,
            timeout=timeout_seconds,
            max_stdout_bytes=1024 * 1024,
            max_stderr_bytes=1024 * 1024,
        )
    except ValidationError:
        return False
    if timed_out or code != 0:
        return False
    return bool(out.strip())


def resolve_scope(
    project_root: str,
    *,
    base_ref: str | None = None,
    target_ref: str = "HEAD",
    timeout_seconds: float = 10.0,
) -> ReleaseScope:
    target_sha = _rev_parse(project_root, target_ref, timeout_seconds=timeout_seconds)
    dirty = _is_dirty(project_root, timeout_seconds=timeout_seconds)

    if target_sha is None:
        target = ReleaseRef(ref=target_ref, sha="unknown")
        return ReleaseScope(
            base=None,
            target=target,
            dirty_worktree=dirty,
            confidence=ScopeConfidence.NO_BASELINE,
            rationale=f"could not resolve target ref {target_ref!r}; is this a git repository?",
        )
    target = ReleaseRef(ref=target_ref, sha=target_sha)

    if base_ref is not None:
        base_sha = _rev_parse(project_root, base_ref, timeout_seconds=timeout_seconds)
        if base_sha is None:
            return ReleaseScope(
                base=None,
                target=target,
                dirty_worktree=dirty,
                confidence=ScopeConfidence.NO_BASELINE,
                rationale=f"explicit base ref {base_ref!r} could not be resolved",
            )
        return ReleaseScope(
            base=ReleaseRef(ref=base_ref, sha=base_sha),
            target=target,
            dirty_worktree=dirty,
            confidence=ScopeConfidence.EXPLICIT,
            rationale="explicit base and target refs supplied by the caller",
        )

    latest_tag = resolve_latest_tag(project_root, timeout_seconds=timeout_seconds)
    if latest_tag is None:
        return ReleaseScope(
            base=None,
            target=target,
            dirty_worktree=dirty,
            confidence=ScopeConfidence.NO_BASELINE,
            rationale="no version-like tag exists and no --base was given; no baseline invented",
        )
    base_sha = _rev_parse(project_root, latest_tag, timeout_seconds=timeout_seconds)
    if base_sha is None:
        return ReleaseScope(
            base=None,
            target=target,
            dirty_worktree=dirty,
            confidence=ScopeConfidence.NO_BASELINE,
            rationale=f"latest tag {latest_tag!r} could not be resolved to a commit",
        )
    return ReleaseScope(
        base=ReleaseRef(ref=latest_tag, sha=base_sha),
        target=target,
        dirty_worktree=dirty,
        confidence=ScopeConfidence.RESOLVED_TAG,
        rationale=f"using latest usable release tag {latest_tag!r} as the base",
    )
