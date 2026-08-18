from __future__ import annotations

import subprocess

import pytest

from projectkaizen.release import (
    ChangeCategory,
    ReadinessOutcome,
    ScopeConfidence,
    classify_change,
    compare_contracts,
    compute_changed_files,
    evaluate_readiness,
    list_tags,
    parse_version_tag,
    resolve_latest_tag,
    resolve_scope,
    run_operational_checklist,
)
from projectkaizen.release.models import ChangedFile, ChangeType, ReleaseFinding, ReleaseFindingStatus

_GIT_AVAILABLE = subprocess.run(["git", "--version"], capture_output=True).returncode == 0  # noqa: S603, S607
pytestmark = pytest.mark.skipif(not _GIT_AVAILABLE, reason="git not available")


def _git(*args: str, cwd: str) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)  # noqa: S603, S607


def _init_repo(tmp_path) -> str:
    root = str(tmp_path)
    _git("init", "-q", cwd=root)
    _git("config", "user.email", "test@example.com", cwd=root)
    _git("config", "user.name", "Test", cwd=root)
    return root


# --- tags.py -----------------------------------------------------------------


def test_parse_version_tag_accepts_v_prefix():
    assert parse_version_tag("v1.2.3") == (1, 2, 3)


def test_parse_version_tag_accepts_bare():
    assert parse_version_tag("1.2.3") == (1, 2, 3)


def test_parse_version_tag_rejects_non_version():
    assert parse_version_tag("latest") is None


def test_list_tags_empty_repo(tmp_path):
    root = _init_repo(tmp_path)
    assert list_tags(root) == ()


def test_resolve_latest_tag_none_when_no_tags(tmp_path):
    root = _init_repo(tmp_path)
    (tmp_path / "a.txt").write_text("x", encoding="utf-8")
    _git("add", "-A", cwd=root)
    _git("commit", "-q", "-m", "initial", cwd=root)
    assert resolve_latest_tag(root) is None


def test_resolve_latest_tag_picks_highest_version(tmp_path):
    root = _init_repo(tmp_path)
    (tmp_path / "a.txt").write_text("x", encoding="utf-8")
    _git("add", "-A", cwd=root)
    _git("commit", "-q", "-m", "initial", cwd=root)
    for tag in ("v1.0.0", "v1.2.0", "v1.10.0", "not-a-version"):
        _git("tag", tag, cwd=root)
    assert resolve_latest_tag(root) == "v1.10.0"


# --- scope.py ------------------------------------------------------------


def test_scope_no_baseline_when_not_a_git_repo(tmp_path):
    scope = resolve_scope(str(tmp_path))
    assert scope.confidence == ScopeConfidence.NO_BASELINE
    assert scope.base is None


def test_scope_no_baseline_when_no_tags(tmp_path):
    root = _init_repo(tmp_path)
    (tmp_path / "a.txt").write_text("x", encoding="utf-8")
    _git("add", "-A", cwd=root)
    _git("commit", "-q", "-m", "initial", cwd=root)
    scope = resolve_scope(root)
    assert scope.confidence == ScopeConfidence.NO_BASELINE
    assert "no baseline invented" in scope.rationale


def test_scope_never_invents_a_baseline_from_first_commit(tmp_path):
    root = _init_repo(tmp_path)
    (tmp_path / "a.txt").write_text("x", encoding="utf-8")
    _git("add", "-A", cwd=root)
    _git("commit", "-q", "-m", "initial", cwd=root)
    scope = resolve_scope(root)
    # even though a commit exists, without an explicit base or a tag,
    # no baseline may be silently assumed
    assert scope.base is None


def test_scope_explicit_refs(tmp_path):
    root = _init_repo(tmp_path)
    (tmp_path / "a.txt").write_text("v1", encoding="utf-8")
    _git("add", "-A", cwd=root)
    _git("commit", "-q", "-m", "first", cwd=root)
    (tmp_path / "a.txt").write_text("v2", encoding="utf-8")
    _git("add", "-A", cwd=root)
    _git("commit", "-q", "-m", "second", cwd=root)

    scope = resolve_scope(root, base_ref="HEAD~1", target_ref="HEAD")
    assert scope.confidence == ScopeConfidence.EXPLICIT
    assert scope.base is not None
    assert scope.base.sha != scope.target.sha


def test_scope_detects_dirty_worktree(tmp_path):
    root = _init_repo(tmp_path)
    (tmp_path / "a.txt").write_text("v1", encoding="utf-8")
    _git("add", "-A", cwd=root)
    _git("commit", "-q", "-m", "first", cwd=root)
    (tmp_path / "a.txt").write_text("uncommitted change", encoding="utf-8")
    scope = resolve_scope(root, base_ref="HEAD", target_ref="HEAD")
    assert scope.dirty_worktree is True


def test_scope_resolves_via_latest_tag(tmp_path):
    root = _init_repo(tmp_path)
    (tmp_path / "a.txt").write_text("v1", encoding="utf-8")
    _git("add", "-A", cwd=root)
    _git("commit", "-q", "-m", "first", cwd=root)
    _git("tag", "v1.0.0", cwd=root)
    (tmp_path / "a.txt").write_text("v2", encoding="utf-8")
    _git("add", "-A", cwd=root)
    _git("commit", "-q", "-m", "second", cwd=root)

    scope = resolve_scope(root)
    assert scope.confidence == ScopeConfidence.RESOLVED_TAG
    assert scope.base.ref == "v1.0.0"


def test_scope_annotated_tag_resolves_to_commit_sha_not_tag_object(tmp_path):
    # git rev-parse on an *annotated* tag returns the tag object's own SHA
    # unless dereferenced; ReleaseRef.sha must always be a real commit sha.
    root = _init_repo(tmp_path)
    (tmp_path / "a.txt").write_text("v1", encoding="utf-8")
    _git("add", "-A", cwd=root)
    _git("commit", "-q", "-m", "first", cwd=root)
    commit_sha = subprocess.run(  # noqa: S603, S607
        ["git", "-C", root, "rev-parse", "HEAD"], capture_output=True, text=True, check=True
    ).stdout.strip()
    _git("tag", "-a", "v1.0.0", "-m", "annotated", cwd=root)
    tag_object_sha = subprocess.run(  # noqa: S603, S607
        ["git", "-C", root, "rev-parse", "v1.0.0"], capture_output=True, text=True, check=True
    ).stdout.strip()
    assert tag_object_sha != commit_sha  # sanity: this really is an annotated tag

    scope = resolve_scope(root, base_ref="v1.0.0", target_ref="HEAD")
    assert scope.base.sha == commit_sha
    assert scope.base.sha != tag_object_sha


def test_scope_unresolvable_explicit_base_falls_back_to_no_baseline(tmp_path):
    root = _init_repo(tmp_path)
    (tmp_path / "a.txt").write_text("v1", encoding="utf-8")
    _git("add", "-A", cwd=root)
    _git("commit", "-q", "-m", "first", cwd=root)
    scope = resolve_scope(root, base_ref="does-not-exist-ref")
    assert scope.confidence == ScopeConfidence.NO_BASELINE


# --- diff.py -----------------------------------------------------------------


def test_classify_change_pyproject():
    categories = classify_change("pyproject.toml")
    assert ChangeCategory.PACKAGE_METADATA in categories
    assert ChangeCategory.DEPENDENCIES in categories


def test_classify_change_unrecognized_is_other():
    assert classify_change("random_notes.txt") == (ChangeCategory.OTHER,)


def test_compute_changed_files_detects_modification(tmp_path):
    root = _init_repo(tmp_path)
    (tmp_path / "a.py").write_text("v1", encoding="utf-8")
    _git("add", "-A", cwd=root)
    _git("commit", "-q", "-m", "first", cwd=root)
    base_sha = subprocess.run(  # noqa: S603, S607
        ["git", "-C", root, "rev-parse", "HEAD"], capture_output=True, text=True, check=True
    ).stdout.strip()
    (tmp_path / "a.py").write_text("v2", encoding="utf-8")
    _git("add", "-A", cwd=root)
    _git("commit", "-q", "-m", "second", cwd=root)
    target_sha = subprocess.run(  # noqa: S603, S607
        ["git", "-C", root, "rev-parse", "HEAD"], capture_output=True, text=True, check=True
    ).stdout.strip()

    changed = compute_changed_files(root, base_sha=base_sha, target_sha=target_sha)
    assert len(changed) == 1
    assert changed[0].path == "a.py"
    assert changed[0].change_type == ChangeType.MODIFIED


# --- checklist.py --------------------------------------------------------


def test_checklist_emits_needs_confirmation_for_config_change():
    changed = (ChangedFile(path="config.py", change_type=ChangeType.MODIFIED, categories=(ChangeCategory.CONFIG,)),)
    findings = run_operational_checklist(changed)
    assert len(findings) == 1
    assert findings[0].status == ReleaseFindingStatus.NEEDS_CONFIRMATION


def test_checklist_no_findings_for_other_category():
    changed = (ChangedFile(path="notes.txt", change_type=ChangeType.MODIFIED, categories=(ChangeCategory.OTHER,)),)
    assert run_operational_checklist(changed) == ()


def test_checklist_no_findings_for_empty_diff():
    assert run_operational_checklist(()) == ()


def test_checklist_deterministic_ordering():
    changed = (
        ChangedFile(path="a.py", change_type=ChangeType.MODIFIED, categories=(ChangeCategory.CONFIG,)),
        ChangedFile(path="b.py", change_type=ChangeType.MODIFIED, categories=(ChangeCategory.DEPENDENCIES,)),
    )
    f1 = run_operational_checklist(changed)
    f2 = run_operational_checklist(tuple(reversed(changed)))
    assert [f.category for f in f1] == [f.category for f in f2]


# --- contracts.py --------------------------------------------------------


def test_compare_contracts_none_when_files_missing(tmp_path):
    root = _init_repo(tmp_path)
    (tmp_path / "a.txt").write_text("x", encoding="utf-8")
    _git("add", "-A", cwd=root)
    _git("commit", "-q", "-m", "first", cwd=root)
    sha = subprocess.run(  # noqa: S603, S607
        ["git", "-C", root, "rev-parse", "HEAD"], capture_output=True, text=True, check=True
    ).stdout.strip()
    findings = compare_contracts(root, base_sha=sha, target_sha=sha)
    assert findings == ()


def test_compare_contracts_detects_removed_cli_subcommand(tmp_path):
    root = _init_repo(tmp_path)
    cli_dir = tmp_path / "src" / "projectkaizen"
    cli_dir.mkdir(parents=True)
    (cli_dir / "cli.py").write_text(
        'subparsers.add_parser("inspect")\nsubparsers.add_parser("plan")\n', encoding="utf-8"
    )
    _git("add", "-A", cwd=root)
    _git("commit", "-q", "-m", "first", cwd=root)
    base_sha = subprocess.run(  # noqa: S603, S607
        ["git", "-C", root, "rev-parse", "HEAD"], capture_output=True, text=True, check=True
    ).stdout.strip()

    (cli_dir / "cli.py").write_text('subparsers.add_parser("inspect")\n', encoding="utf-8")
    _git("add", "-A", cwd=root)
    _git("commit", "-q", "-m", "remove plan", cwd=root)
    target_sha = subprocess.run(  # noqa: S603, S607
        ["git", "-C", root, "rev-parse", "HEAD"], capture_output=True, text=True, check=True
    ).stdout.strip()

    findings = compare_contracts(root, base_sha=base_sha, target_sha=target_sha)
    cli_finding = next(f for f in findings if f.category == ChangeCategory.CLI_CONTRACT)
    assert cli_finding.status == ReleaseFindingStatus.BLOCKED


# --- readiness.py --------------------------------------------------------


def test_readiness_needs_confirmation_when_no_baseline(tmp_path):
    root = _init_repo(tmp_path)
    scope = resolve_scope(root)
    report = evaluate_readiness(root, scope=scope)
    assert report.outcome == ReadinessOutcome.NEEDS_CONFIRMATION
    assert report.findings == ()


def test_readiness_no_blocker_found_for_identical_refs(tmp_path):
    root = _init_repo(tmp_path)
    (tmp_path / "a.txt").write_text("x", encoding="utf-8")
    _git("add", "-A", cwd=root)
    _git("commit", "-q", "-m", "first", cwd=root)
    scope = resolve_scope(root, base_ref="HEAD", target_ref="HEAD")
    report = evaluate_readiness(root, scope=scope)
    assert report.outcome == ReadinessOutcome.NO_BLOCKER_FOUND
    assert "not a safety guarantee" in report.rationale


def test_readiness_blocked_by_removed_cli_subcommand(tmp_path):
    root = _init_repo(tmp_path)
    cli_dir = tmp_path / "src" / "projectkaizen"
    cli_dir.mkdir(parents=True)
    (cli_dir / "cli.py").write_text(
        'subparsers.add_parser("inspect")\nsubparsers.add_parser("plan")\n', encoding="utf-8"
    )
    _git("add", "-A", cwd=root)
    _git("commit", "-q", "-m", "first", cwd=root)
    base_sha = subprocess.run(  # noqa: S603, S607
        ["git", "-C", root, "rev-parse", "HEAD"], capture_output=True, text=True, check=True
    ).stdout.strip()

    (cli_dir / "cli.py").write_text('subparsers.add_parser("inspect")\n', encoding="utf-8")
    _git("add", "-A", cwd=root)
    _git("commit", "-q", "-m", "remove plan", cwd=root)

    scope = resolve_scope(root, base_ref=base_sha, target_ref="HEAD")
    report = evaluate_readiness(root, scope=scope)
    assert report.outcome == ReadinessOutcome.BLOCKED


def test_readiness_never_claims_safe_language():
    # documentation-level regression: the phrase "no blocker" must never be
    # rendered as an unqualified safety claim anywhere in this module.
    from projectkaizen import human

    text = human.plain_readiness_outcome(ReadinessOutcome.NO_BLOCKER_FOUND)
    assert "guaranteed" not in text.lower() or "not" in text.lower()


def test_release_finding_requires_valid_fields():
    from projectkaizen.exceptions import ValidationError

    with pytest.raises(ValidationError):
        ReleaseFinding(
            id="",
            category=ChangeCategory.CONFIG,
            title="t",
            description="d",
            status=ReleaseFindingStatus.NEEDS_CONFIRMATION,
        )
