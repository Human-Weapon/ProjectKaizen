"""RepositoryHygieneAnalyzer: small deterministic hygiene heuristics.

Checks: missing ``.gitignore``, and generated-artifact directories that
would be swept up by a naive ``git add -A`` because ``.gitignore`` does not
exclude them. This is a lightweight check, not a git-tracked-file audit —
ProjectKaizen never invokes git itself here (no execution of target
tooling; spec section 25).
"""

from __future__ import annotations

from ..config import KaizenConfig
from ..models import AnalysisResult, Confidence, Severity
from ..walker import WalkResult, read_text_bounded
from ._shared import complete, make_evidence, make_finding

ANALYZER_NAME = "RepositoryHygieneAnalyzer"


def analyze(walk: WalkResult, *, config: KaizenConfig, project_area_id: str = "root") -> AnalysisResult:
    findings = []
    relative_paths = {f.relative_path for f in walk.files}
    has_gitignore = ".gitignore" in relative_paths
    gitignore_text = ""
    if has_gitignore:
        gitignore_file = next(f for f in walk.files if f.relative_path == ".gitignore")
        try:
            gitignore_text = read_text_bounded(
                gitignore_file.absolute_path, max_bytes=config.walker_max_bytes_per_file
            ).text
        except OSError:
            gitignore_text = ""

    if not has_gitignore:
        findings.append(
            make_finding(
                analyzer=ANALYZER_NAME,
                project_area_id=project_area_id,
                title="missing .gitignore",
                description="No .gitignore found; generated artifacts (caches, build output) risk being committed.",
                evidence=(make_evidence(ANALYZER_NAME, "missing_file", "no .gitignore", "walk"),),
                severity=Severity.LOW,
                confidence=Confidence.HIGH,
                estimated_effort="small",
                expected_impact="repo_cleanliness",
                tags=("repository_hygiene", "gitignore"),
            )
        )
    else:
        # walker already excludes common cache dirs from its own listing, so
        # detect presence via top-level directory names it still surfaces
        # (build/, dist/, *.egg-info are not in DEFAULT_IGNORED_DIRS).
        top_level_dirs = {p.split("/", 1)[0] for p in relative_paths if "/" in p}
        present_generated = sorted(d for d in ("dist", "build") if d in top_level_dirs and d not in gitignore_text)
        if present_generated:
            findings.append(
                make_finding(
                    analyzer=ANALYZER_NAME,
                    project_area_id=project_area_id,
                    title="generated build directories not excluded by .gitignore",
                    description=(
                        f"directories {present_generated} exist in the tree but are not mentioned in "
                        ".gitignore; verify they are not accidentally tracked."
                    ),
                    evidence=(make_evidence(ANALYZER_NAME, "generated_dir", str(present_generated), ".gitignore"),),
                    severity=Severity.LOW,
                    confidence=Confidence.LOW,
                    affected_paths=tuple(present_generated),
                    estimated_effort="small",
                    expected_impact="repo_cleanliness",
                    tags=("repository_hygiene", "artifacts"),
                )
            )

    env_files = sorted(p for p in relative_paths if p == ".env" or p.endswith("/.env"))
    if env_files:
        findings.append(
            make_finding(
                analyzer=ANALYZER_NAME,
                project_area_id=project_area_id,
                title="'.env' file present in project tree",
                description=(
                    f"found {env_files}; if this is tracked in version control it may leak secrets. "
                    "ProjectKaizen only checks the filename, not file contents or git-tracked status."
                ),
                evidence=(make_evidence(ANALYZER_NAME, "env_file", str(env_files), "walk"),),
                severity=Severity.HIGH,
                confidence=Confidence.LOW,
                affected_paths=tuple(env_files),
                estimated_effort="small",
                expected_impact="secret_exposure_risk",
                tags=("repository_hygiene", "secrets"),
            )
        )

    return complete(ANALYZER_NAME, findings)
