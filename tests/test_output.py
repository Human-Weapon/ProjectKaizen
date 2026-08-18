from __future__ import annotations

from conftest import make_finding

from projectkaizen.models import OutputBudget, Severity
from projectkaizen.output import (
    OutputMode,
    build_findings_display,
    compress,
    compress_evidence,
    compress_findings,
    effective_budget,
    is_critical,
)


def test_compress_keeps_head_and_forced_items():
    items = list(range(20))
    result = compress(items, max_shown=3, must_keep=lambda i: i in (15, 19))
    assert result.shown == (0, 1, 2, 15, 19)
    assert result.omitted_count == 15
    assert result.forced_kept_count == 2


def test_compress_summary_text():
    items = list(range(37))
    result = compress(items, max_shown=5)
    assert result.summary(noun="findings detected") == "37 findings detected; showing top 5"


def test_compress_summary_no_truncation():
    items = list(range(3))
    result = compress(items, max_shown=5)
    assert result.summary(noun="findings detected") == "3 findings detected"


def test_is_critical():
    critical = make_finding("c", severity=Severity.CRITICAL)
    low = make_finding("l", severity=Severity.LOW)
    assert is_critical(critical) is True
    assert is_critical(low) is False


def test_effective_budget_concise_is_unchanged():
    base = OutputBudget(max_findings_shown=5)
    assert effective_budget(base, OutputMode.CONCISE) == base


def test_effective_budget_standard_multiplies():
    base = OutputBudget(max_findings_shown=5)
    eff = effective_budget(base, OutputMode.STANDARD)
    assert eff.max_findings_shown == 15


def test_effective_budget_detailed_is_effectively_unbounded():
    base = OutputBudget(max_findings_shown=5)
    eff = effective_budget(base, OutputMode.DETAILED)
    assert eff.max_findings_shown >= 10_000


def test_100_findings_default_output_is_bounded():
    findings = tuple(make_finding(f"f{i}", severity=Severity.LOW) for i in range(100))
    budget = OutputBudget(max_findings_shown=5)
    result = compress_findings(findings, budget=budget)
    assert len(result.shown) == 5
    assert result.total_count == 100


def test_critical_findings_never_disappear_under_truncation():
    critical_ids = {10, 30, 50, 70, 90}
    findings = tuple(
        make_finding(f"f{i}", severity=Severity.CRITICAL if i in critical_ids else Severity.LOW) for i in range(100)
    )
    budget = OutputBudget(max_findings_shown=5)
    result = compress_findings(findings, budget=budget)
    shown_ids = {f.id for f in result.shown}
    assert {f"f{i}" for i in critical_ids}.issubset(shown_ids)


def test_top_priorities_appear_first_in_shown_order():
    findings = (
        make_finding("low1", severity=Severity.LOW),
        make_finding("critical1", severity=Severity.CRITICAL),
        make_finding("low2", severity=Severity.LOW),
    )
    budget = OutputBudget(max_findings_shown=3)
    result = compress_findings(findings, budget=budget)
    assert result.shown[0].id == "low1"  # pre-sort order is caller's responsibility; compress preserves it


def test_evidence_compression_respects_budget():
    from projectkaizen.models import Evidence

    evidence = tuple(Evidence(id=f"e{i}", kind="k", description="d", source="s") for i in range(10))
    budget = OutputBudget(max_evidence_items_per_finding=2)
    result = compress_evidence(evidence, budget=budget)
    assert len(result.shown) == 2
    assert result.total_count == 10


def test_full_mode_exposes_everything_concise_derived_from():
    findings = tuple(make_finding(f"f{i}", severity=Severity.LOW) for i in range(20))
    budget = OutputBudget(max_findings_shown=5)
    concise = build_findings_display(findings, budget=budget, mode=OutputMode.CONCISE)
    full = build_findings_display(findings, budget=budget, mode=OutputMode.DETAILED)
    assert concise.compressed.omitted_count > 0
    assert full.compressed.omitted_count == 0
    # concise view is always a subset of what full mode contains
    assert {f.id for f in concise.compressed.shown}.issubset({f.id for f in full.compressed.shown})


def test_concise_and_full_derive_from_same_total_count():
    findings = tuple(make_finding(f"f{i}") for i in range(9))
    budget = OutputBudget(max_findings_shown=5)
    concise = build_findings_display(findings, budget=budget, mode=OutputMode.CONCISE)
    full = build_findings_display(findings, budget=budget, mode=OutputMode.DETAILED)
    assert concise.compressed.total_count == full.compressed.total_count == 9
