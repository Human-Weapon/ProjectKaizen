"""Deterministic operational-readiness checklist over a set of changed files.

Only emits a finding where the diff actually gives *some* concrete signal
(spec section 19's distinction): "no access to AWS" alone is a tool
limitation, not a finding; "TARGET changed persistence.py and repository
evidence cannot confirm production migration ran" is diff-driven and
belongs to the caller as NEEDS_CONFIRMATION. Categories with zero evidence
in the diff produce no finding at all rather than manufactured
UNABLE_TO_VERIFY noise for things nobody asked about.

Known limitation: classification is by filename/path pattern, so
infrastructure concerns invisible in a Python source diff — queue
contracts, cache invalidation, CDN/asset provisioning, rollout ordering —
are not detected unless a changed file's *name* hints at them. This module
does not claim broader coverage than that.
"""

from __future__ import annotations

from ..fingerprint import deterministic_id
from .models import ChangeCategory, ChangedFile, ReleaseFinding, ReleaseFindingStatus

_CATEGORY_GUIDANCE: dict[ChangeCategory, str] = {
    ChangeCategory.PERSISTED_SCHEMA: (
        "persisted-schema-related file(s) changed; confirm migration ordering, backward "
        "read/write compatibility during a rolling deploy, and rollback plan"
    ),
    ChangeCategory.MIGRATIONS: (
        "migration-related file(s) changed; confirm backfill/expand-migrate-contract ordering "
        "and that destructive steps run last, if any"
    ),
    ChangeCategory.CONFIG: (
        "config-related file(s) changed; confirm defaults and required keys are provisioned in deployment targets"
    ),
    ChangeCategory.ENV_VARS: (
        "environment-variable-related file(s) changed; confirm new/removed variables are provisioned before deploy"
    ),
    ChangeCategory.DEPENDENCIES: (
        "dependency declarations changed; confirm compatibility across the supported Python/platform matrix"
    ),
    ChangeCategory.PACKAGE_METADATA: (
        "package metadata changed; confirm version/classifiers/entry points are intentional for this release"
    ),
    ChangeCategory.PYTHON_SUPPORT: (
        "declared Python support changed; confirm CI still covers the claimed version range"
    ),
    ChangeCategory.CLI_CONTRACT: (
        "CLI surface changed; confirm downstream scripts/automation invoking it are not broken"
    ),
    ChangeCategory.PUBLIC_API: (
        "public API surface changed; confirm this is an intentional, documented compatibility "
        "break or is backward-compatible"
    ),
    ChangeCategory.COMPATIBILITY: (
        "a file affecting compatibility changed; confirm consumers pinned to the prior contract still function"
    ),
    ChangeCategory.ARTIFACTS: (
        "build/CI artifact configuration changed; confirm build/test/publish paths still match reality"
    ),
    ChangeCategory.ERROR_BEHAVIOR: (
        "error-handling code changed; confirm callers relying on specific exception types/exit codes still work"
    ),
    ChangeCategory.CONCURRENCY_LIFECYCLE: (
        "process/concurrency lifecycle code changed; confirm timeout/cleanup behavior under real load"
    ),
}


def run_operational_checklist(changed_files: tuple[ChangedFile, ...]) -> tuple[ReleaseFinding, ...]:
    paths_by_category: dict[ChangeCategory, list[str]] = {}
    for changed in changed_files:
        for category in changed.categories:
            if category == ChangeCategory.OTHER:
                continue
            paths_by_category.setdefault(category, []).append(changed.path)

    findings = []
    for category in sorted(paths_by_category, key=lambda c: c.value):
        paths = tuple(sorted(paths_by_category[category]))
        guidance = _CATEGORY_GUIDANCE.get(category)
        if guidance is None:
            continue
        finding_id = deterministic_id("release_finding", category.value, ",".join(paths))
        findings.append(
            ReleaseFinding(
                id=finding_id,
                category=category,
                title=f"{category.value}: confirmation needed",
                description=guidance,
                status=ReleaseFindingStatus.NEEDS_CONFIRMATION,
                evidence=(f"{len(paths)} file(s) changed in this category",),
                affected_paths=paths,
            )
        )
    return tuple(findings)
