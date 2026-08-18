from __future__ import annotations

import pytest

from projectkaizen.analyzers import code_health, documentation
from projectkaizen.exceptions import ValidationError
from projectkaizen.models import AnalysisStatus
from projectkaizen.scale.decomposition import (
    analyze_partition,
    filter_files,
    inventory,
    merge_results,
    partition_by_directory,
    partition_by_size,
    verify_sample,
)
from projectkaizen.walker import walk_project


def _make_repo(tmp_path, dirs: int, files_per_dir: int):
    for d in range(dirs):
        for i in range(files_per_dir):
            f = tmp_path / f"pkg{d}" / f"mod{i}.py"
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text(f"# TODO fix\ndef f{i}(): return {i}\n", encoding="utf-8")


def test_inventory_matches_walk_files(tmp_path):
    _make_repo(tmp_path, 2, 3)
    walk = walk_project(tmp_path, max_files=1000, max_depth=64, max_total_bytes=10_000_000)
    assert inventory(walk) == walk.files


def test_filter_files_by_suffix(tmp_path):
    (tmp_path / "a.py").write_text("x", encoding="utf-8")
    (tmp_path / "b.md").write_text("x", encoding="utf-8")
    walk = walk_project(tmp_path, max_files=1000, max_depth=64, max_total_bytes=10_000_000)
    filtered = filter_files(inventory(walk), suffixes=(".py",))
    assert {f.relative_path for f in filtered} == {"a.py"}


def test_filter_files_by_exclude_prefix(tmp_path):
    (tmp_path / "a.py").write_text("x", encoding="utf-8")
    (tmp_path / "gen_b.py").write_text("x", encoding="utf-8")
    walk = walk_project(tmp_path, max_files=1000, max_depth=64, max_total_bytes=10_000_000)
    filtered = filter_files(inventory(walk), exclude_prefixes=("gen_",))
    assert {f.relative_path for f in filtered} == {"a.py"}


def test_partition_by_directory_respects_max_files(tmp_path):
    _make_repo(tmp_path, dirs=3, files_per_dir=10)
    walk = walk_project(tmp_path, max_files=1000, max_depth=64, max_total_bytes=10_000_000)
    partitions = partition_by_directory(inventory(walk), max_files_per_partition=4)
    assert all(len(p.files) <= 4 for p in partitions)
    assert sum(len(p.files) for p in partitions) == 30


def test_partition_by_directory_deterministic(tmp_path):
    _make_repo(tmp_path, dirs=3, files_per_dir=5)
    walk = walk_project(tmp_path, max_files=1000, max_depth=64, max_total_bytes=10_000_000)
    files = inventory(walk)
    p1 = partition_by_directory(files, max_files_per_partition=5)
    p2 = partition_by_directory(files, max_files_per_partition=5)
    assert [p.id for p in p1] == [p.id for p in p2]


def test_partition_by_size_respects_byte_cap(tmp_path):
    for i in range(10):
        (tmp_path / f"f{i}.py").write_text("x" * 100, encoding="utf-8")
    walk = walk_project(tmp_path, max_files=1000, max_depth=64, max_total_bytes=10_000_000)
    partitions = partition_by_size(inventory(walk), max_bytes_per_partition=250, max_files_per_partition=1000)
    assert all(p.total_bytes <= 250 or len(p.files) == 1 for p in partitions)
    assert sum(len(p.files) for p in partitions) == 10


def test_partition_rejects_invalid_limits(tmp_path):
    walk = walk_project(tmp_path, max_files=1000, max_depth=64, max_total_bytes=10_000_000)
    with pytest.raises(ValidationError):
        partition_by_directory(inventory(walk), max_files_per_partition=0)
    with pytest.raises(ValidationError):
        partition_by_size(inventory(walk), max_bytes_per_partition=0, max_files_per_partition=10)


def test_large_synthetic_repo_end_to_end(tmp_path, config):
    _make_repo(tmp_path, dirs=20, files_per_dir=15)  # 300 files
    walk = walk_project(str(tmp_path), max_files=10000, max_depth=64, max_total_bytes=100_000_000)
    files = inventory(walk)
    partitions = partition_by_directory(files, max_files_per_partition=50)

    results = tuple(
        analyze_partition(p, root=str(tmp_path), config=config, analyzers=(code_health.analyze, documentation.analyze))
        for p in partitions
    )
    merged = merge_results(partitions, results)

    assert merged.total_files == 300
    assert merged.status == AnalysisStatus.COMPLETE
    ids = [f.id for f in merged.findings]
    assert len(ids) == len(set(ids))  # aggregate has no duplicates
    assert merged.findings == tuple(sorted(merged.findings, key=lambda f: f.id))  # deterministic order


def test_merge_results_never_loses_a_critical_finding():
    from projectkaizen.models import Confidence, Evidence, Finding, Severity
    from projectkaizen.scale.decomposition import Partition, PartitionAnalysisResult

    critical = Finding(
        id="crit1",
        project_area_id="root",
        title="critical issue",
        description="d",
        evidence=(Evidence(id="e1", kind="k", description="d", source="s"),),
        severity=Severity.CRITICAL,
        confidence=Confidence.HIGH,
    )
    partitions = (
        Partition(id="p1", strategy="test", files=()),
        Partition(id="p2", strategy="test", files=()),
        Partition(id="p3", strategy="test", files=()),
    )
    results = (
        PartitionAnalysisResult(partition_id="p1", status=AnalysisStatus.COMPLETE, findings=(critical,)),
        PartitionAnalysisResult(partition_id="p2", status=AnalysisStatus.COMPLETE, findings=()),
        PartitionAnalysisResult(partition_id="p3", status=AnalysisStatus.COMPLETE, findings=()),
    )
    merged = merge_results(partitions, results)
    assert critical.id in {f.id for f in merged.findings}


def test_merge_results_flags_incomplete_partitions():
    from projectkaizen.scale.decomposition import Partition, PartitionAnalysisResult

    p1 = Partition(id="p1", strategy="test", files=())
    p2 = Partition(id="p2", strategy="test", files=())
    results = (
        PartitionAnalysisResult(partition_id="p1", status=AnalysisStatus.COMPLETE, findings=()),
        PartitionAnalysisResult(
            partition_id="p2", status=AnalysisStatus.ANALYSIS_INCOMPLETE, findings=(), incomplete_reasons=("x",)
        ),
    )
    merged = merge_results((p1, p2), results)
    assert merged.status == AnalysisStatus.ANALYSIS_INCOMPLETE
    assert merged.incomplete_partition_ids == ("p2",)


def test_verify_sample_deterministic_and_evenly_spaced(tmp_path):
    _make_repo(tmp_path, dirs=10, files_per_dir=2)
    walk = walk_project(tmp_path, max_files=1000, max_depth=64, max_total_bytes=10_000_000)
    partitions = partition_by_directory(inventory(walk), max_files_per_partition=2)
    sample1 = verify_sample(partitions, sample_size=3)
    sample2 = verify_sample(partitions, sample_size=3)
    assert sample1 == sample2
    assert len(sample1) == 3


def test_verify_sample_returns_all_when_sample_size_exceeds_count(tmp_path):
    _make_repo(tmp_path, dirs=2, files_per_dir=2)
    walk = walk_project(tmp_path, max_files=1000, max_depth=64, max_total_bytes=10_000_000)
    partitions = partition_by_directory(inventory(walk), max_files_per_partition=2)
    sample = verify_sample(partitions, sample_size=1000)
    assert len(sample) == len(partitions)


def test_verify_sample_rejects_invalid_size(tmp_path):
    walk = walk_project(tmp_path, max_files=1000, max_depth=64, max_total_bytes=10_000_000)
    with pytest.raises(ValidationError):
        verify_sample(partition_by_directory(inventory(walk)), sample_size=0)
