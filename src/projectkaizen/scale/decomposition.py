"""Deterministic decomposition for repositories too large to analyze as
one unit.

    inventory -> filter -> partition -> analyze_partition -> merge_results
                                              (spot-check: verify_sample)

No LLM, no subagent, no recursive model calls: partitioning is pure
bin-packing over already-walked file metadata, and each partition is
analyzed by the same deterministic analyzer functions used everywhere else
in ProjectKaizen. AgentGear may choose to run partitions in parallel
externally — this module only defines the units; it does not orchestrate
execution itself (spec section 13).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from ..exceptions import ValidationError
from ..fingerprint import deterministic_id
from ..models import AnalysisResult, AnalysisStatus, Finding
from ..walker import WalkedFile, WalkResult

DEFAULT_MAX_FILES_PER_PARTITION = 200
DEFAULT_MAX_BYTES_PER_PARTITION = 5_000_000


@dataclass(frozen=True, slots=True)
class Partition:
    id: str
    strategy: str
    files: tuple[WalkedFile, ...]

    @property
    def total_bytes(self) -> int:
        return sum(f.size_bytes for f in self.files)


@dataclass(frozen=True, slots=True)
class PartitionAnalysisResult:
    partition_id: str
    status: AnalysisStatus
    findings: tuple[Finding, ...]
    incomplete_reasons: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class DecompositionResult:
    status: AnalysisStatus
    partitions: tuple[Partition, ...]
    findings: tuple[Finding, ...]
    incomplete_partition_ids: tuple[str, ...]
    total_files: int


def inventory(walk: WalkResult) -> tuple[WalkedFile, ...]:
    """The full, already-deterministic file list from a walk."""
    return walk.files


def filter_files(
    files: tuple[WalkedFile, ...],
    *,
    suffixes: tuple[str, ...] | None = None,
    exclude_prefixes: tuple[str, ...] = (),
) -> tuple[WalkedFile, ...]:
    result = files
    if suffixes:
        result = tuple(f for f in result if f.relative_path.endswith(suffixes))
    if exclude_prefixes:
        result = tuple(f for f in result if not f.relative_path.startswith(exclude_prefixes))
    return result


def _make_partition(strategy: str, index: int, files: tuple[WalkedFile, ...]) -> Partition:
    paths_key = ",".join(f.relative_path for f in files)
    partition_id = deterministic_id("partition", strategy, str(index), paths_key)
    return Partition(id=partition_id, strategy=strategy, files=files)


def partition_by_directory(
    files: tuple[WalkedFile, ...],
    *,
    max_files_per_partition: int = DEFAULT_MAX_FILES_PER_PARTITION,
) -> tuple[Partition, ...]:
    """Group by top-level directory (deterministic order), splitting any
    oversized directory into multiple bounded, still-deterministic chunks.
    """
    if max_files_per_partition < 1:
        raise ValidationError("max_files_per_partition must be >= 1")

    by_dir: dict[str, list[WalkedFile]] = {}
    for f in sorted(files, key=lambda f: f.relative_path):
        top = f.relative_path.split("/", 1)[0] if "/" in f.relative_path else ""
        by_dir.setdefault(top, []).append(f)

    partitions: list[Partition] = []
    index = 0
    for directory in sorted(by_dir):
        group = by_dir[directory]
        for start in range(0, len(group), max_files_per_partition):
            chunk = tuple(group[start : start + max_files_per_partition])
            partitions.append(_make_partition("directory", index, chunk))
            index += 1
    return tuple(partitions)


def partition_by_size(
    files: tuple[WalkedFile, ...],
    *,
    max_bytes_per_partition: int = DEFAULT_MAX_BYTES_PER_PARTITION,
    max_files_per_partition: int = DEFAULT_MAX_FILES_PER_PARTITION,
) -> tuple[Partition, ...]:
    """Greedy bin-packing over files sorted by path, bounded by both bytes
    and count. Deterministic: same input always yields the same bins.
    """
    if max_bytes_per_partition < 1 or max_files_per_partition < 1:
        raise ValidationError("max_bytes_per_partition and max_files_per_partition must be >= 1")

    partitions: list[Partition] = []
    current: list[WalkedFile] = []
    current_bytes = 0
    index = 0
    for f in sorted(files, key=lambda f: f.relative_path):
        would_overflow_bytes = current and current_bytes + f.size_bytes > max_bytes_per_partition
        would_overflow_count = len(current) >= max_files_per_partition
        if would_overflow_bytes or would_overflow_count:
            partitions.append(_make_partition("size", index, tuple(current)))
            index += 1
            current = []
            current_bytes = 0
        current.append(f)
        current_bytes += f.size_bytes
    if current:
        partitions.append(_make_partition("size", index, tuple(current)))
    return tuple(partitions)


def _synthetic_walk(root: str, partition: Partition) -> WalkResult:
    return WalkResult(
        root=root,
        files=partition.files,
        status=AnalysisStatus.COMPLETE,
        incomplete_reasons=(),
        total_bytes=partition.total_bytes,
        skipped_reparse_points=(),
        skipped_special_files=(),
        skipped_unreadable=(),
    )


AnalyzerFunc = Callable[..., AnalysisResult]


def analyze_partition(
    partition: Partition, *, root: str, config: object, analyzers: tuple[AnalyzerFunc, ...]
) -> PartitionAnalysisResult:
    synthetic_walk = _synthetic_walk(root, partition)
    findings: list[Finding] = []
    incomplete_reasons: list[str] = []
    for analyzer in analyzers:
        result = analyzer(synthetic_walk, config=config)
        findings.extend(result.findings)
        if result.status == AnalysisStatus.ANALYSIS_INCOMPLETE:
            incomplete_reasons.extend(f"{result.analyzer}: {r}" for r in result.incomplete_reasons)
    status = AnalysisStatus.ANALYSIS_INCOMPLETE if incomplete_reasons else AnalysisStatus.COMPLETE
    return PartitionAnalysisResult(
        partition_id=partition.id, status=status, findings=tuple(findings), incomplete_reasons=tuple(incomplete_reasons)
    )


def merge_results(
    partitions: tuple[Partition, ...], partition_results: tuple[PartitionAnalysisResult, ...]
) -> DecompositionResult:
    """Concatenate + deduplicate + deterministically sort. Never truncates —
    output-budget truncation is `output.py`'s job, applied once on the
    fully merged set, so no partition's findings (critical or otherwise)
    are lost before that stage even sees them.
    """
    seen_ids: set[str] = set()
    merged: list[Finding] = []
    incomplete_ids: list[str] = []
    for result in partition_results:
        if result.status == AnalysisStatus.ANALYSIS_INCOMPLETE:
            incomplete_ids.append(result.partition_id)
        for finding in result.findings:
            if finding.id in seen_ids:
                continue
            seen_ids.add(finding.id)
            merged.append(finding)

    merged.sort(key=lambda f: f.id)
    total_files = sum(len(p.files) for p in partitions)
    status = AnalysisStatus.ANALYSIS_INCOMPLETE if incomplete_ids else AnalysisStatus.COMPLETE
    return DecompositionResult(
        status=status,
        partitions=partitions,
        findings=tuple(merged),
        incomplete_partition_ids=tuple(sorted(incomplete_ids)),
        total_files=total_files,
    )


def verify_sample(partitions: tuple[Partition, ...], *, sample_size: int) -> tuple[Partition, ...]:
    """Deterministic, evenly-spaced spot-check sample — never random."""
    if sample_size < 1:
        raise ValidationError("sample_size must be >= 1")
    ordered = tuple(sorted(partitions, key=lambda p: p.id))
    if sample_size >= len(ordered):
        return ordered
    step = len(ordered) / sample_size
    indices = sorted({int(i * step) for i in range(sample_size)})
    return tuple(ordered[i] for i in indices)
