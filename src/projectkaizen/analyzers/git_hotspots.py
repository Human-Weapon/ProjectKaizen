"""Git hotspot analysis: where does real change repeatedly happen.

Not wired into the default 8-analyzer registry (``ALL_ANALYZERS`` /
``run_all``) — it is the one analyzer that runs a real subprocess (``git
log``, read-only, offline, bounded by timeout via ``process.run_bounded``),
so it is opt-in rather than something every ``inspect`` silently executes.
Call ``analyze_git_hotspots`` directly when hotspot evidence is wanted.

Signal, not verdict: a hotspot is a file that changes often and/or
recently — a priority for human inspection, never an automatic defect
finding. "High churn == bad" is exactly the leap this module refuses to make
(spec section 6). Churn here is approximated by commit count touching a
file, not added/removed line counts — line-level ``--numstat`` parsing adds
significant fragility for a proxy signal that commit frequency already
captures reasonably well; this is a documented simplification, not an
oversight.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..exceptions import ValidationError
from ..models import AnalysisStatus
from ..process import run_bounded
from ..walker import DEFAULT_IGNORED_DIRS

_LOG_FORMAT = "%H\x1f%ct"
_UNIT_SEP = "\x1f"

#: recency component reaches 0 once a file is this many seconds older than
#: the most recent commit in the whole history (deterministic reference
#: point — never wall-clock time; see module docstring on determinism).
DEFAULT_RECENCY_WINDOW_SECONDS = 90 * 24 * 3600
#: commit_count saturates the frequency component at this count
DEFAULT_FREQUENCY_SATURATION = 20


@dataclass(frozen=True, slots=True)
class FileHotspot:
    relative_path: str
    commit_count: int
    first_commit_epoch: int
    most_recent_commit_epoch: int
    score: float
    frequency_component: float
    recency_component: float


@dataclass(frozen=True, slots=True)
class GitHotspotResult:
    status: AnalysisStatus
    hotspots: tuple[FileHotspot, ...]
    commits_analyzed: int
    incomplete_reasons: tuple[str, ...] = ()


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


#: broader than walker.DEFAULT_IGNORED_DIRS on purpose: RepositoryHygieneAnalyzer
#: *wants* to see a committed dist/build directory (to flag it), but hotspot
#: ranking should never let one dominate just because it's regenerated
#: every commit.
_HOTSPOT_IGNORED_DIRS = DEFAULT_IGNORED_DIRS | {"dist", "build", "vendor", "target", "out"}


def _is_generated_or_vendor_path(path: str) -> bool:
    """Excludes committed build/cache/vendor output from hotspot ranking.

    Self-adversarial finding: a generated or vendored path that happens to
    be committed and regenerated every commit (a lockfile, a build
    artifact) would otherwise dominate the ranking by pure commit count and
    drown out real source hotspots — "high churn" from a machine, not from
    people making decisions, is not the signal this module is for.
    """
    parts = path.split("/")
    return any(part in _HOTSPOT_IGNORED_DIRS for part in parts)


def _parse_log(stdout_text: str) -> list[tuple[str, int, list[str]]]:
    commits: list[tuple[str, int, list[str]]] = []
    current_hash: str | None = None
    current_epoch: int | None = None
    current_files: list[str] = []
    for line in stdout_text.splitlines():
        if _UNIT_SEP in line:
            if current_hash is not None:
                commits.append((current_hash, current_epoch or 0, current_files))
            head, _, epoch_text = line.partition(_UNIT_SEP)
            current_hash = head
            try:
                current_epoch = int(epoch_text)
            except ValueError:
                current_epoch = 0
            current_files = []
        elif line.strip():
            current_files.append(line.strip())
    if current_hash is not None:
        commits.append((current_hash, current_epoch or 0, current_files))
    return commits


def analyze_git_hotspots(
    project_root: str,
    *,
    timeout_seconds: float = 15.0,
    max_commits: int = 5000,
    recency_window_seconds: int = DEFAULT_RECENCY_WINDOW_SECONDS,
    frequency_saturation: int = DEFAULT_FREQUENCY_SATURATION,
) -> GitHotspotResult:
    try:
        code, out, err, timed_out, out_trunc, _err_trunc, _duration = run_bounded(
            [
                "git",
                "-C",
                project_root,
                "log",
                f"--max-count={max_commits}",
                f"--pretty=format:{_LOG_FORMAT}",
                "--name-only",
            ],
            cwd=None,
            env=None,
            timeout=timeout_seconds,
            max_stdout_bytes=64 * 1024 * 1024,
            max_stderr_bytes=1024 * 1024,
        )
    except ValidationError:
        return GitHotspotResult(
            status=AnalysisStatus.FAILED,
            hotspots=(),
            commits_analyzed=0,
            incomplete_reasons=("git executable not found",),
        )

    if timed_out:
        return GitHotspotResult(
            status=AnalysisStatus.ANALYSIS_INCOMPLETE,
            hotspots=(),
            commits_analyzed=0,
            incomplete_reasons=(f"git log timed out after {timeout_seconds}s",),
        )
    if code != 0:
        stderr_text = err.decode("utf-8", errors="replace").strip()
        lowered = stderr_text.lower()
        if "does not have any commits yet" in lowered:
            # a real, valid repository with no history yet is not a failure
            # or an incompleteness — there is simply nothing to report.
            return GitHotspotResult(status=AnalysisStatus.COMPLETE, hotspots=(), commits_analyzed=0)
        reason = "not a git repository" if "not a git repository" in lowered else f"git log failed: {stderr_text[:200]}"
        return GitHotspotResult(
            status=AnalysisStatus.ANALYSIS_INCOMPLETE, hotspots=(), commits_analyzed=0, incomplete_reasons=(reason,)
        )

    stdout_text = out.decode("utf-8", errors="replace")
    commits = _parse_log(stdout_text)

    incomplete_reasons: list[str] = []
    if out_trunc:
        incomplete_reasons.append("git log output was truncated by the byte cap")
    if len(commits) >= max_commits:
        incomplete_reasons.append(f"history limited to the most recent {max_commits} commit(s)")

    if not commits:
        return GitHotspotResult(
            status=AnalysisStatus.COMPLETE,
            hotspots=(),
            commits_analyzed=0,
            incomplete_reasons=tuple(incomplete_reasons),
        )

    per_file: dict[str, list[int]] = {}
    for _commit_hash, epoch, files in commits:
        for path in files:
            if _is_generated_or_vendor_path(path):
                continue
            per_file.setdefault(path, []).append(epoch)

    most_recent_overall = max(epoch for _h, epoch, _f in commits)

    hotspots = []
    for path, epochs in per_file.items():
        commit_count = len(epochs)
        first_epoch = min(epochs)
        last_epoch = max(epochs)
        age_seconds = max(0, most_recent_overall - last_epoch)
        recency_component = _clamp01(1.0 - age_seconds / recency_window_seconds)
        frequency_component = _clamp01(commit_count / frequency_saturation)
        score = 0.5 * frequency_component + 0.5 * recency_component
        hotspots.append(
            FileHotspot(
                relative_path=path,
                commit_count=commit_count,
                first_commit_epoch=first_epoch,
                most_recent_commit_epoch=last_epoch,
                score=score,
                frequency_component=frequency_component,
                recency_component=recency_component,
            )
        )

    hotspots.sort(key=lambda h: (-h.score, h.relative_path))
    status = AnalysisStatus.ANALYSIS_INCOMPLETE if incomplete_reasons else AnalysisStatus.COMPLETE
    return GitHotspotResult(
        status=status,
        hotspots=tuple(hotspots),
        commits_analyzed=len(commits),
        incomplete_reasons=tuple(incomplete_reasons),
    )
