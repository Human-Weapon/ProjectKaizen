"""ProjectKaizen CLI.

Exit codes (stable, documented, tested — see README "Exit codes"):

    0  success, nothing requires attention
    1  actionable findings exist / comparison REJECTed / stopping not stable
    2  invalid input, config, or arguments
    3  analysis incomplete, or comparison INCONCLUSIVE/DEFERred
    4  persisted state is corrupt
    5  a verification command failed or timed out
    6  a path escaped its trusted root

``--json`` prints pure JSON to stdout and nothing else — no banners, no
human narration mixed in.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from ._version import __version__
from .analyzers import run_all
from .compare import compare as compare_candidates
from .config import KaizenConfig
from .exceptions import ConfigurationError, ProjectKaizenError
from .fingerprint import deterministic_id
from .history import HistoryLog
from .human import (
    plain_change_category,
    plain_finding_status,
    plain_readiness_outcome,
    plain_stopping_reasons,
    plain_verdict,
    plain_viability,
)
from .jsonutil import to_jsonable
from .models import (
    AnalysisResult,
    AnalysisStatus,
    Baseline,
    Candidate,
    Finding,
    RootCauseStatus,
    Severity,
    ViabilityStatus,
)
from .output import OutputMode, build_findings_display
from .persistence import read_json_document, write_json_document
from .prioritize import rank_findings
from .release import evaluate_readiness, resolve_scope
from .stopping import evaluate_stopping
from .viability import ViabilityInputs, assess_viability
from .walker import walk_project

EXIT_SUCCESS = 0
EXIT_ATTENTION = 1
EXIT_INVALID_INPUT = 2
EXIT_INCOMPLETE = 3
EXIT_CORRUPT_STATE = 4
EXIT_VERIFICATION_FAILURE = 5
EXIT_PATH_ESCAPE = 6

_AGENTOPS_DIRNAME = ".agentops/kaizen"

#: heuristic mapping from finding severity/confidence to viability inputs,
#: used only by the `plan` command where no external benefit/effort/risk
#: measurement is available. Documented, deterministic, not "magic":
#: severity drives expected benefit, confidence carries straight through,
#: effort/risk default to a flat mid estimate since analyzers do not
#: estimate implementation cost.
_SEVERITY_BENEFIT = {
    Severity.CRITICAL: 0.9,
    Severity.HIGH: 0.7,
    Severity.MEDIUM: 0.45,
    Severity.LOW: 0.2,
    Severity.INFO: 0.05,
}
_HEURISTIC_EFFORT = 0.2
_HEURISTIC_RISK = 0.1


def _agentops_dir(project_root: Path) -> Path:
    return project_root / _AGENTOPS_DIRNAME


def _finding_dict(finding: Finding) -> dict[str, Any]:
    return {
        "id": finding.id,
        "project_area_id": finding.project_area_id,
        "title": finding.title,
        "description": finding.description,
        "severity": finding.severity,
        "confidence": finding.confidence,
        "affected_paths": finding.affected_paths,
        "estimated_effort": finding.estimated_effort,
        "expected_impact": finding.expected_impact,
        "implementation_risk": finding.implementation_risk,
        "source": finding.source,
        "tags": finding.tags,
        "evidence": [
            {"id": e.id, "kind": e.kind, "description": e.description, "source": e.source} for e in finding.evidence
        ],
    }


def _analysis_result_dict(result: AnalysisResult) -> dict[str, Any]:
    return {
        "analyzer": result.analyzer,
        "status": result.status,
        "incomplete_reasons": result.incomplete_reasons,
        "finding_count": len(result.findings),
    }


def _run_analysis(
    project_root: Path, config: KaizenConfig
) -> tuple[Any, tuple[AnalysisResult, ...], tuple[Finding, ...]]:
    walk = walk_project(
        project_root,
        max_files=config.walker_max_files,
        max_depth=config.walker_max_depth,
        max_total_bytes=config.walker_max_total_bytes,
    )
    results = run_all(walk, config=config)
    findings = tuple(f for r in results for f in r.findings)
    _reject_duplicate_finding_ids(findings)
    return walk, results, findings


def _reject_duplicate_finding_ids(findings: tuple[Finding, ...]) -> None:
    """A colliding id would otherwise silently drop one finding wherever
    callers key by id (e.g. ``{f.id: f for f in findings}``); fail loudly
    instead of losing data quietly.
    """
    seen: dict[str, Finding] = {}
    for finding in findings:
        collision = seen.get(finding.id)
        if collision is not None:
            raise ProjectKaizenError(
                f"duplicate finding id {finding.id!r} from {collision.source!r} and {finding.source!r}"
            )
        seen[finding.id] = finding


def _overall_status(walk_status: AnalysisStatus, results: tuple[AnalysisResult, ...]) -> AnalysisStatus:
    if walk_status == AnalysisStatus.ANALYSIS_INCOMPLETE or any(
        r.status == AnalysisStatus.ANALYSIS_INCOMPLETE for r in results
    ):
        return AnalysisStatus.ANALYSIS_INCOMPLETE
    return AnalysisStatus.COMPLETE


def _print_json(payload: dict[str, Any]) -> None:
    jsonable = to_jsonable(payload, name="cli_output")
    sys.stdout.write(json.dumps(jsonable, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n")


def cmd_inspect(args: argparse.Namespace, config: KaizenConfig) -> int:
    project_root = Path(args.path)
    walk, results, findings = _run_analysis(project_root, config)
    ranked = rank_findings(findings)
    findings_by_id = {f.id: f for f in findings}
    ordered = tuple(findings_by_id[r.finding_id] for r in ranked)

    mode = OutputMode.DETAILED if args.full else OutputMode.CONCISE
    display = build_findings_display(ordered, budget=config.output_budget, mode=mode)
    status = _overall_status(walk.status, results)

    if args.json:
        _print_json(
            {
                "command": "inspect",
                "status": status,
                "walk_incomplete_reasons": walk.incomplete_reasons,
                "analyzers": [_analysis_result_dict(r) for r in results],
                "findings_total": len(findings),
                "findings_shown": [_finding_dict(f) for f in display.compressed.shown],
            }
        )
    else:
        print(f"status: {status.value}")
        if walk.incomplete_reasons:
            print(f"walk incomplete: {'; '.join(walk.incomplete_reasons)}")
        print(display.summary)
        for f in display.compressed.shown:
            print(f"  [{f.severity.value:>8}] {f.title} ({f.id})")

    if args.persist:
        _agentops_dir(project_root).mkdir(parents=True, exist_ok=True)
        write_json_document(
            _agentops_dir(project_root) / "last_inspect.json",
            root=_agentops_dir(project_root),
            kind="inspect_result",
            schema_version=1,
            payload={
                "status": status.value,
                "findings": [_finding_dict(f) for f in ordered],
            },
        )

    if status == AnalysisStatus.ANALYSIS_INCOMPLETE:
        return EXIT_INCOMPLETE
    return EXIT_ATTENTION if findings else EXIT_SUCCESS


def cmd_findings(args: argparse.Namespace, config: KaizenConfig) -> int:
    return cmd_inspect(args, config)


def cmd_plan(args: argparse.Namespace, config: KaizenConfig) -> int:
    project_root = Path(args.path)
    walk, results, findings = _run_analysis(project_root, config)
    status = _overall_status(walk.status, results)

    viabilities = {}
    for f in findings:
        inputs = ViabilityInputs(
            root_cause_status=RootCauseStatus.POSSIBLE,
            expected_benefit=_SEVERITY_BENEFIT[f.severity],
            effort_score=_HEURISTIC_EFFORT,
            risk_score=_HEURISTIC_RISK,
            confidence=f.confidence,
            reversible=True,
        )
        viabilities[f.id] = assess_viability(inputs)

    ranked = rank_findings(findings, viabilities=viabilities)
    findings_by_id = {f.id: f for f in findings}
    actionable_statuses = (ViabilityStatus.VIABLE, ViabilityStatus.MARGINAL)
    actionable = [r for r in ranked if viabilities[r.finding_id].status in actionable_statuses]
    ordered_actionable = tuple(findings_by_id[r.finding_id] for r in actionable)

    mode = OutputMode.DETAILED if args.full else OutputMode.CONCISE
    display = build_findings_display(ordered_actionable, budget=config.output_budget, mode=mode)

    if args.json:
        _print_json(
            {
                "command": "plan",
                "status": status,
                "actionable_total": len(ordered_actionable),
                "plan_shown": [
                    {
                        **_finding_dict(f),
                        "viability": viabilities[f.id].status,
                        "viability_rationale": viabilities[f.id].rationale,
                    }
                    for f in display.compressed.shown
                ],
            }
        )
    else:
        print(f"status: {status.value}")
        print(display.summary.replace("findings detected", "improvement opportunities"))
        for f in display.compressed.shown:
            v = viabilities[f.id]
            print(f"  [{plain_viability(v.status)}] {f.title}")
            if args.full:
                print(f"      technical: {v.status.value} - {v.rationale}")

    if status == AnalysisStatus.ANALYSIS_INCOMPLETE:
        return EXIT_INCOMPLETE
    return EXIT_ATTENTION if ordered_actionable else EXIT_SUCCESS


def cmd_baseline(args: argparse.Namespace, config: KaizenConfig) -> int:
    project_root = Path(args.path)
    metrics: dict[str, float] = {}
    for item in args.metric or []:
        if "=" not in item:
            print(f"error: --metric must be name=value, got {item!r}", file=sys.stderr)
            return EXIT_INVALID_INPUT
        name, _, raw_value = item.partition("=")
        try:
            metrics[name] = float(raw_value)
        except ValueError:
            print(f"error: metric {name!r} value {raw_value!r} is not a number", file=sys.stderr)
            return EXIT_INVALID_INPUT
    if not metrics:
        print("error: at least one --metric name=value is required", file=sys.stderr)
        return EXIT_INVALID_INPUT

    baseline = Baseline(id=args.id, metrics=metrics, captured_from=args.captured_from or "manual")
    out_dir = _agentops_dir(project_root)
    out_dir.mkdir(parents=True, exist_ok=True)
    write_json_document(
        out_dir / "baseline.json",
        root=out_dir,
        kind="baseline",
        schema_version=1,
        payload={"id": baseline.id, "metrics": dict(baseline.metrics), "captured_from": baseline.captured_from},
    )
    if args.json:
        _print_json({"command": "baseline", "id": baseline.id, "metrics": dict(baseline.metrics)})
    else:
        print(f"baseline {baseline.id} saved: {dict(baseline.metrics)}")
    return EXIT_SUCCESS


def _load_metrics_file(path: Path) -> dict[str, Any]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ConfigurationError(f"cannot read {path}: {exc}") from exc
    if not isinstance(raw, dict):
        raise ConfigurationError(f"{path} must contain a JSON object")
    return raw


def cmd_compare(args: argparse.Namespace, config: KaizenConfig) -> int:
    baseline_raw = _load_metrics_file(Path(args.baseline_file))
    candidate_raw = _load_metrics_file(Path(args.candidate_file))

    baseline = Baseline(
        id=baseline_raw.get("id", "baseline"),
        metrics=baseline_raw["metrics"],
        captured_from=baseline_raw.get("captured_from", "file"),
    )
    candidate = Candidate(
        id=candidate_raw.get("id", "candidate"),
        baseline_id=candidate_raw.get("baseline_id", baseline.id),
        improvement_id=candidate_raw.get("improvement_id", "adhoc"),
        metrics=candidate_raw["metrics"],
        captured_from=candidate_raw.get("captured_from", "file"),
    )
    # Direction is metric-specific (e.g. latency: lower is better; accuracy:
    # higher is better) and cannot be guessed, so either file may declare it
    # explicitly; unspecified metrics default to "higher is better".
    higher_is_better = {**baseline_raw.get("higher_is_better", {}), **candidate_raw.get("higher_is_better", {})}

    result = compare_candidates(
        comparison_id=f"{baseline.id}_vs_{candidate.id}",
        baseline=baseline,
        candidate=candidate,
        config=config,
        higher_is_better=higher_is_better,
    )

    if args.record:
        project_root = Path(args.path) if args.path else Path.cwd()
        out_dir = _agentops_dir(project_root)
        out_dir.mkdir(parents=True, exist_ok=True)
        history_path = out_dir / "history.json"
        log = HistoryLog(max_entries=config.history_max_entries)
        try:
            existing = read_json_document(
                history_path, root=out_dir, expected_kind="history_log", expected_schema_version=1
            )
            for entry in existing.get("entries", []):
                log.add(
                    id=entry["id"],
                    improvement_id=entry["improvement_id"],
                    problem=entry["problem"],
                    decision=entry["decision"],
                    solution=entry["solution"],
                    regression_test=entry["regression_test"],
                    result=entry["result"],
                )
        except FileNotFoundError:
            pass
        # Content-derived, not just baseline/candidate ids: two distinct
        # comparisons that happen to reuse the same (default) ids must not
        # collide and silently drop one from history; an identical repeat
        # comparison, by contrast, is naturally idempotent here.
        history_id = deterministic_id("history", result.id, result.verdict.value, result.rationale)
        if not log.has(history_id):
            log.add(
                id=history_id,
                improvement_id=candidate.improvement_id,
                problem=f"compare {baseline.id} vs {candidate.id}",
                decision=result.verdict.value,
                solution="see comparison deltas",
                regression_test="metric comparison against minimum meaningful delta + hard gates",
                result=result.rationale,
            )
        write_json_document(
            history_path,
            root=out_dir,
            kind="history_log",
            schema_version=1,
            payload={"entries": [_history_entry_dict(e) for e in log.entries(newest_first=False)]},
        )

    if args.json:
        _print_json(
            {
                "command": "compare",
                "verdict": result.verdict,
                "rationale": result.rationale,
                "hard_gate_violations": result.hard_gate_violations,
                "deltas": [
                    {
                        "metric": d.metric,
                        "baseline_value": d.baseline_value,
                        "candidate_value": d.candidate_value,
                        "absolute_delta": d.absolute_delta,
                        "meaningful": d.meaningful,
                    }
                    for d in result.deltas
                ],
            }
        )
    else:
        print(plain_verdict(result.verdict))
        print(result.rationale)
        if result.rollback_guidance:
            print(result.rollback_guidance)
        if args.full:
            print(f"technical verdict: {result.verdict.value}")

    if result.verdict.value == "accept":
        return EXIT_SUCCESS
    if result.verdict.value == "reject":
        return EXIT_ATTENTION
    return EXIT_INCOMPLETE


def _history_entry_dict(entry: Any) -> dict[str, Any]:
    return {
        "id": entry.id,
        "improvement_id": entry.improvement_id,
        "problem": entry.problem,
        "decision": entry.decision,
        "solution": entry.solution,
        "regression_test": entry.regression_test,
        "result": entry.result,
    }


def cmd_status(args: argparse.Namespace, config: KaizenConfig) -> int:
    project_root = Path(args.path)
    walk, results, findings = _run_analysis(project_root, config)
    status = _overall_status(walk.status, results)

    viabilities = {}
    for f in findings:
        inputs = ViabilityInputs(
            root_cause_status=RootCauseStatus.POSSIBLE,
            expected_benefit=_SEVERITY_BENEFIT[f.severity],
            effort_score=_HEURISTIC_EFFORT,
            risk_score=_HEURISTIC_RISK,
            confidence=f.confidence,
            reversible=True,
        )
        viabilities[f.id] = assess_viability(inputs)

    decision = evaluate_stopping(remaining_findings=findings, viabilities=viabilities, config=config)

    if args.json:
        _print_json(
            {
                "command": "status",
                "analysis_status": status,
                "kaizen_stable": decision.stable,
                "reasons": decision.reasons,
                "rationale": decision.rationale,
                "findings_total": len(findings),
            }
        )
    else:
        if decision.stable:
            print("Nothing worthwhile left to improve right now.")
        else:
            print("There is still worthwhile improvement work to do.")
        if decision.reasons:
            print(f"Why: {plain_stopping_reasons(decision.reasons)}.")
        if args.full:
            print(f"technical status: analysis={status.value} kaizen_stable={decision.stable}")
            if decision.reasons:
                print(f"technical reasons: {', '.join(r.value for r in decision.reasons)}")
            print(f"technical rationale: {decision.rationale}")

    if status == AnalysisStatus.ANALYSIS_INCOMPLETE:
        return EXIT_INCOMPLETE
    return EXIT_SUCCESS if decision.stable else EXIT_ATTENTION


def cmd_history(args: argparse.Namespace, config: KaizenConfig) -> int:
    project_root = Path(args.path)
    out_dir = _agentops_dir(project_root)
    history_path = out_dir / "history.json"
    if not history_path.exists():
        if args.json:
            _print_json({"command": "history", "entries_total": 0, "entries_shown": []})
        else:
            print("no history recorded yet (run `projectkaizen compare --record` to build history)")
        return EXIT_SUCCESS

    data = read_json_document(history_path, root=out_dir, expected_kind="history_log", expected_schema_version=1)
    entries = data.get("entries", [])
    limit = config.output_budget.max_history_items_shown
    shown = entries if args.full else entries[-limit:]
    shown = list(reversed(shown))

    if args.json:
        _print_json({"command": "history", "entries_total": len(entries), "entries_shown": shown})
    else:
        total = len(entries)
        if len(shown) < total:
            print(f"{total} history entries; showing latest {len(shown)}")
        else:
            print(f"{total} history entries")
        for entry in shown:
            print(f"  [{entry['decision']}] {entry['problem']} -> {entry['result']}")
    return EXIT_SUCCESS


def cmd_validate(args: argparse.Namespace, config: KaizenConfig) -> int:
    target = Path(args.artifact)
    try:
        raw = json.loads(target.read_text(encoding="utf-8"))
    except OSError as exc:
        print(f"error: cannot read {target}: {exc}", file=sys.stderr)
        return EXIT_INVALID_INPUT
    except json.JSONDecodeError as exc:
        print(f"error: {target} is not valid JSON: {exc}", file=sys.stderr)
        return EXIT_INVALID_INPUT

    if isinstance(raw, dict) and {"kind", "schema_version", "data"} <= set(raw):
        payload = {
            "command": "validate",
            "artifact_kind": "persisted_document",
            "kind": raw["kind"],
            "schema_version": raw["schema_version"],
            "valid": True,
        }
        if args.json:
            _print_json(payload)
        else:
            print(f"valid persisted document: kind={raw['kind']} schema_version={raw['schema_version']}")
        return EXIT_SUCCESS

    try:
        KaizenConfig.from_mapping(raw)
    except ProjectKaizenError as exc:
        if args.json:
            _print_json({"command": "validate", "artifact_kind": "config", "valid": False, "error": str(exc)})
        else:
            print(f"invalid config: {exc}", file=sys.stderr)
        return EXIT_INVALID_INPUT

    if args.json:
        _print_json({"command": "validate", "artifact_kind": "config", "valid": True})
    else:
        print(f"valid KaizenConfig: {target}")
    return EXIT_SUCCESS


def cmd_release_readiness(args: argparse.Namespace, config: KaizenConfig) -> int:
    project_root = args.path
    scope = resolve_scope(project_root, base_ref=args.base, target_ref=args.target or "HEAD")
    report = evaluate_readiness(project_root, scope=scope)

    if args.json:
        _print_json(
            {
                "command": "release-readiness",
                "outcome": report.outcome,
                "rationale": report.rationale,
                "confidence": report.confidence,
                "changed_file_count": report.changed_file_count,
                "scope": {
                    "base": {"ref": report.scope.base.ref, "sha": report.scope.base.sha} if report.scope.base else None,
                    "target": {"ref": report.scope.target.ref, "sha": report.scope.target.sha},
                    "dirty_worktree": report.scope.dirty_worktree,
                    "confidence": report.scope.confidence,
                },
                "findings": [
                    {
                        "id": f.id,
                        "category": f.category,
                        "title": f.title,
                        "description": f.description,
                        "status": f.status,
                        "affected_paths": f.affected_paths,
                    }
                    for f in report.findings
                ],
            }
        )
    else:
        print(plain_readiness_outcome(report.outcome))
        if report.scope.base:
            base, target = report.scope.base, report.scope.target
            print(f"Compared {base.ref} to {target.ref} ({report.changed_file_count} file(s) changed).")
        else:
            print(report.rationale)
        for f in report.findings:
            print(f"  [{plain_finding_status(f.status)}] {plain_change_category(f.category)}: {f.description}")
        if args.full:
            print(f"technical outcome: {report.outcome.value}")
            print(f"technical rationale: {report.rationale}")

    if report.outcome.value == "blocked":
        return EXIT_ATTENTION
    if report.outcome.value == "needs_confirmation":
        return EXIT_INCOMPLETE
    return EXIT_SUCCESS


def _build_global_opts_parser(*, suppress_defaults: bool) -> argparse.ArgumentParser:
    """--json/--full/--config work both before AND after the subcommand.

    `projectkaizen --json inspect .` and `projectkaizen inspect . --json`
    are both natural things to type; restricting these to one position is a
    usability trap, not a meaningful constraint, so this parser is attached
    as `parents=[...]` to the top-level parser and to every subparser.

    argparse merges a subparser's namespace onto the top-level namespace by
    overwriting every attribute the subparser defines — including with its
    own *default* when the flag wasn't given a second time. Without
    `suppress_defaults`, `projectkaizen --json inspect .` would silently
    lose `--json` (the subparser's unset default clobbers it). Passing
    `suppress_defaults=True` for the per-subcommand copy means "only touch
    this attribute if the user actually typed the flag here."
    """
    default = argparse.SUPPRESS if suppress_defaults else False
    none_default = argparse.SUPPRESS if suppress_defaults else None
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--json", action="store_true", default=default, help="emit pure JSON to stdout only")
    parser.add_argument(
        "--full",
        "--detailed",
        dest="full",
        action="store_true",
        default=default,
        help="show full detail, not the concise default",
    )
    parser.add_argument("--config", dest="config_path", default=none_default, help="path to a KaizenConfig JSON file")
    return parser


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="projectkaizen",
        description="Continuous-improvement toolkit.",
        parents=[_build_global_opts_parser(suppress_defaults=False)],
    )
    parser.add_argument("--version", action="version", version=f"projectkaizen {__version__}")

    subparsers = parser.add_subparsers(dest="command", required=True)

    for name in ("inspect", "findings", "plan", "status", "history"):
        sp = subparsers.add_parser(name, parents=[_build_global_opts_parser(suppress_defaults=True)])
        sp.add_argument("path", nargs="?", default=".")
        if name == "inspect":
            sp.add_argument("--persist", action="store_true", help="write findings to .agentops/kaizen/")

    baseline_parser = subparsers.add_parser("baseline", parents=[_build_global_opts_parser(suppress_defaults=True)])
    baseline_parser.add_argument("path", nargs="?", default=".")
    baseline_parser.add_argument("--id", default="baseline")
    baseline_parser.add_argument("--metric", action="append", help="name=value, may be repeated")
    baseline_parser.add_argument("--captured-from", dest="captured_from", default=None)

    compare_parser = subparsers.add_parser("compare", parents=[_build_global_opts_parser(suppress_defaults=True)])
    compare_parser.add_argument("baseline_file")
    compare_parser.add_argument("candidate_file")
    compare_parser.add_argument(
        "--record", action="store_true", help="append the result to .agentops/kaizen/history.json"
    )
    compare_parser.add_argument("--path", default=None, help="project root for --record (default: cwd)")

    validate_parser = subparsers.add_parser("validate", parents=[_build_global_opts_parser(suppress_defaults=True)])
    validate_parser.add_argument("artifact")

    release_parser = subparsers.add_parser(
        "release-readiness", parents=[_build_global_opts_parser(suppress_defaults=True)]
    )
    release_parser.add_argument("path", nargs="?", default=".")
    release_parser.add_argument("--base", default=None, help="explicit base ref (default: latest usable tag, if any)")
    release_parser.add_argument("--target", default=None, help="explicit target ref (default: HEAD)")

    return parser


_HANDLERS = {
    "inspect": cmd_inspect,
    "findings": cmd_findings,
    "plan": cmd_plan,
    "baseline": cmd_baseline,
    "compare": cmd_compare,
    "status": cmd_status,
    "history": cmd_history,
    "validate": cmd_validate,
    "release-readiness": cmd_release_readiness,
}


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        config = KaizenConfig.load_file(args.config_path) if args.config_path else KaizenConfig()
    except ProjectKaizenError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_INVALID_INPUT

    handler = _HANDLERS[args.command]
    try:
        return handler(args, config)
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_INVALID_INPUT
    except ProjectKaizenError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return exc.exit_code


if __name__ == "__main__":
    sys.exit(main())
