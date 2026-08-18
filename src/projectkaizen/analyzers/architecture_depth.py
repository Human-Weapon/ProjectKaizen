"""ArchitectureDepthAnalyzer: conservative, AST-based shallow-module signals.

Deliberately does *not* use an implementation-LOC / interface-LOC ratio as
a depth proxy — that metric rewards padding a function with busywork and
punishes a genuinely simple, deep one. Instead this looks for two
structural, low-false-positive patterns using ``ast`` (parsing only, never
executing the target — spec section 25):

* **pass-through functions** — a function whose entire body is a single
  ``return`` of a call that forwards its own parameters unchanged. One such
  function is often a legitimate facade; several in the same module,
  outside ``__init__.py`` (where re-exporting is the normal, intended job),
  is a signal the module may not be pulling its weight.
* **shallow wrapper classes** — a class where most methods are pass-through
  delegation to a single wrapped attribute, with no added behavior.

Every finding requires multiple corroborating instances, never a single
regex/AST match, and confidence is capped at MEDIUM — this is a heuristic
about *likely* shallowness, not a proof of bad design.
"""

from __future__ import annotations

import ast

from ..config import KaizenConfig
from ..models import AnalysisResult, Confidence, Severity
from ..walker import WalkResult
from ._shared import complete, incomplete, make_evidence, make_finding, read_files_text

ANALYZER_NAME = "ArchitectureDepthAnalyzer"

MIN_PASSTHROUGH_FUNCTIONS = 3
MIN_WRAPPER_METHODS = 3
WRAPPER_DELEGATION_RATIO = 0.8


def _is_passthrough_function(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    body = [stmt for stmt in node.body if not (isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant))]
    if len(body) != 1 or not isinstance(body[0], ast.Return) or body[0].value is None:
        return False
    call = body[0].value
    if not isinstance(call, ast.Call):
        return False
    own_params = [a.arg for a in node.args.args if a.arg != "self"]
    if not own_params:
        return False
    call_arg_names = [a.id for a in call.args if isinstance(a, ast.Name)]
    return call_arg_names == own_params


def _find_passthrough_functions(tree: ast.Module) -> list[str]:
    names = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and _is_passthrough_function(node):
            names.append(node.name)
    return names


def _find_shallow_wrapper_classes(tree: ast.Module) -> list[tuple[str, int, int]]:
    """Returns (class_name, delegating_method_count, total_method_count).

    Dunder methods (``__init__`` in particular) are excluded from the
    count: a constructor almost never looks like pure delegation, so
    counting it would structurally bias the ratio against ever detecting a
    real wrapper class.
    """
    results = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        methods = [
            n
            for n in node.body
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and not n.name.startswith("__")
        ]
        if len(methods) < MIN_WRAPPER_METHODS:
            continue
        delegating = sum(1 for m in methods if _is_passthrough_function(m))
        if delegating / len(methods) >= WRAPPER_DELEGATION_RATIO:
            results.append((node.name, delegating, len(methods)))
    return results


def analyze(walk: WalkResult, *, config: KaizenConfig, project_area_id: str = "root") -> AnalysisResult:
    findings = []
    parse_errors: list[str] = []
    py_files = read_files_text(walk, suffixes=(".py",), max_bytes_per_file=config.walker_max_bytes_per_file)

    for path, text in sorted(py_files.items()):
        if path.endswith("__init__.py"):
            continue
        try:
            tree = ast.parse(text, filename=path)
        except SyntaxError:
            parse_errors.append(path)
            continue

        passthrough = _find_passthrough_functions(tree)
        if len(passthrough) >= MIN_PASSTHROUGH_FUNCTIONS:
            findings.append(
                make_finding(
                    analyzer=ANALYZER_NAME,
                    project_area_id=project_area_id,
                    title=f"multiple pass-through functions in {path}",
                    description=(
                        f"{len(passthrough)} function(s) in {path} do nothing but forward their arguments "
                        f"unchanged to another call: {sorted(passthrough)[:10]}. May indicate a shallow module "
                        "whose interface doesn't earn its keep — or a legitimate facade; verify before acting."
                    ),
                    evidence=(make_evidence(ANALYZER_NAME, "passthrough_functions", str(sorted(passthrough)), path),),
                    severity=Severity.INFO,
                    confidence=Confidence.LOW,
                    affected_paths=(path,),
                    estimated_effort="medium",
                    expected_impact="architecture_depth",
                    tags=("architecture", "depth", "passthrough"),
                )
            )

        for class_name, delegating, total in _find_shallow_wrapper_classes(tree):
            findings.append(
                make_finding(
                    analyzer=ANALYZER_NAME,
                    project_area_id=project_area_id,
                    title=f"shallow wrapper class {class_name} in {path}",
                    description=(
                        f"{class_name} in {path} has {delegating}/{total} methods that only forward arguments "
                        "unchanged with no added logic — consistent with a thin wrapper. Wrapper classes are "
                        "sometimes the right seam (e.g. an adapter at a real boundary); this is a signal to "
                        "verify there's a real reason, not a verdict."
                    ),
                    evidence=(
                        make_evidence(ANALYZER_NAME, "wrapper_class", f"{delegating}/{total} delegating methods", path),
                    ),
                    severity=Severity.INFO,
                    confidence=Confidence.MEDIUM,
                    affected_paths=(path,),
                    estimated_effort="medium",
                    expected_impact="architecture_depth",
                    tags=("architecture", "depth", "wrapper"),
                )
            )

    if parse_errors:
        return incomplete(ANALYZER_NAME, findings, tuple(f"could not parse {p}" for p in sorted(parse_errors)))
    return complete(ANALYZER_NAME, findings)
