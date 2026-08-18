# ProjectKaizen v0.1.0 — Pre-First-Adversarial-Audit Candidate

This document records the verified state of ProjectKaizen at the commit
below. It is a candidacy record, not a release: no tag, no GitHub Release,
no PyPI publish has been made.

## Candidate

- Implementation commit: `670d47f587b06acd7b88a10ce7bf3f2bcd623140`
- Repository: https://github.com/Human-Weapon/ProjectKaizen
- Branch: `main`
- Version declared in `src/projectkaizen/_version.py`: `0.1.0`

## Recovery from prior session

A prior checkpoint commit (`4fa46bd`) left six primitive modules
(`_version.py`, `exceptions.py`, `numbers.py`, `jsonutil.py`, `paths.py`,
`process.py`, 539 lines total). All six were inspected, found correct and
consistent with this spec (strict validation, no `shell=True`, defensive
path containment, bounded subprocess execution), and preserved unmodified
except for ruff lint fixes (`contextlib.suppress`, an explicit `taskkill`
path lookup) applied during the quality pass. Everything else — domain
models, the improvement graph, config, viability, prioritization, compare,
stopping, history, persistence, the filesystem walker, all 8 analyzers, the
CLI, and the full test suite — was built in this session on top of that
foundation.

## Test results

- `pytest`: **302 passed, 0 failed, 0 skipped** (local run and CI, both
  Windows and Ubuntu, Python 3.10/3.11/3.12)
- Branch coverage: **93.54%** (gate: ≥90%, enforced via
  `--cov-fail-under=90` in `pyproject.toml` and a dedicated CI job)
- Notable real (non-mocked) regression coverage:
  - real Windows junction creation + escape rejection (`test_paths.py`,
    `test_walker.py`)
  - real subprocess timeout + tree kill (`test_process.py`,
    0.3s real timeout)
  - real corrupt-JSON quarantine on disk (`test_persistence.py`)
  - real CLI invoked as a subprocess (`python -m projectkaizen.cli`) for
    JSON-purity verification (`test_cli.py`)
  - real atomic-write no-leftover-temp-file check
  - invalid-UTF-8 vs. truncated-multibyte-sequence disambiguation

## Quality gates

- Ruff lint (`src` + `tests`): clean
- Ruff format check: clean
- `git diff --check`: clean (no trailing whitespace / conflict markers)
- `git status`: clean at the candidate commit

## Build & packaging

- `python -m build`: wheel + sdist built successfully
- Wheel contents inspected: only `projectkaizen/*` package files and
  standard `dist-info` metadata; no `.git`, caches, `.venv`, coverage
  artifacts, secrets, or sibling-project files
- Sdist contents inspected: `src/`, `tests/`, `README.md`, `LICENSE`,
  `pyproject.toml`, `.gitignore`; same exclusions hold

## Black-box verification

Performed in fresh virtual environments created **outside** the checkout
(`%TEMP%/.../scratchpad/pk-wheel-env*`, `pk-sdist-env`), never activating
the project's own `.venv`:

- **Wheel**, Python 3.12: `pip install dist/*.whl` → `import projectkaizen`
  resolves to the installed `site-packages` copy (verified by path,
  not the source tree) → `projectkaizen --version` → `projectkaizen --help`
  → `projectkaizen --json inspect <sample>` produces valid, parseable JSON.
- **Sdist**, Python 3.10: `pip install dist/*.tar.gz` (built the wheel from
  source under uv) → same import/version/inspect checks pass.
- **Standalone check**: `pip list` in both fresh environments shows exactly
  one package, `projectkaizen` — no PromptGraph, AgentGear, SkillGuard, or
  AgentBench present or required, and no other runtime dependency at all.

## Sample workflow

`docs/sample_project/` is a tiny, deliberately imperfect fixture (one
source file with a TODO, a bare `except`, and a non-deterministic call).
Running `inspect` / `plan` / `status` against it demonstrates the full
pipeline end to end, including the viability gate correctly downgrading
most findings to `NOT_WORTH_IT`/`INSUFFICIENT_EVIDENCE` under the CLI's
heuristic mapping while surfacing the one genuinely actionable finding
(missing packaging file) as `VIABLE`.

## CI

- Workflow: `.github/workflows/ci.yml`
- Run verified green: https://github.com/Human-Weapon/ProjectKaizen/actions/runs/32123966222
- Matrix: Windows-latest × Ubuntu-latest, Python 3.10 / 3.11 / 3.12 (6 jobs)
- Plus: `coverage-gate` (Ubuntu, Python 3.12, `--cov-fail-under=90`),
  `ruff lint + format`, `build wheel + sdist` (includes an in-CI fresh-venv
  wheel smoke test)
- All 9 jobs passed on the candidate commit
- **macOS: not verified.** No macOS job exists in CI; nothing about macOS
  support is claimed.

## Self-adversarial findings

A deliberate self-adversarial pass was run against the checklist in the
build spec. One finding was caught by CI itself; the rest were caught and
fixed during local review before the first push.

| # | Finding | Severity | Outcome |
|---|---|---|---|
| 1 | `ImprovementStatus` lifecycle: `validate_transition`'s terminal-state check for `SUPERSEDED` was inverted — it blocked exactly the transitions (terminal → `SUPERSEDED`) it was meant to allow, and silently allowed the opposite. | P2 | Fixed at the root (`models.py`); regression tests added for terminal→SUPERSEDED, non-terminal→SUPERSEDED, and SUPERSEDED→SUPERSEDED (rejected). |
| 2 | CLI `compare` had no way to declare per-metric direction (`latency: lower is better` vs. `accuracy: higher is better`); every metric silently defaulted to "higher is better," which would misclassify a real latency regression as an improvement. | P2 | Fixed: baseline/candidate JSON may declare `"higher_is_better": {...}`; CLI merges and passes it through. Regression test covers both accept and reject with an explicit direction. |
| 3 | `compare --record` raised an uncaught `ValidationError` (duplicate history id) on a second identical comparison, because the history entry id was derived only from `baseline.id`/`candidate.id`, which collide on repeat runs. | P3 | Fixed: history id is now content-derived (includes verdict + rationale) via `deterministic_id`, making an identical repeat idempotent while still keeping two distinct comparisons that happen to reuse default ids from colliding. `HistoryLog.has()` added. |
| 4 | `_load_metrics_file` (used by `compare`) raised the generic `ProjectKaizenError` (exit 1) for a missing/malformed input file, instead of the documented "invalid input" exit code (2). | P4 | Fixed: now raises `ConfigurationError` (exit 2). |
| 5 | `--json`/`--full` only worked when placed *before* the subcommand (`projectkaizen --json inspect .`); placing them after (`projectkaizen inspect . --json`), the more natural way to type it, raised `unrecognized arguments`. Root cause, once fixed for the flag position, exposed a second issue: naively adding the same flags to every subparser causes argparse to silently clobber a top-level value with the subparser's own default when the flag is only given before the subcommand. | P2 | Fixed: shared parent-parser pattern with `argparse.SUPPRESS` defaults on the per-subcommand copy, so a flag is honored regardless of position and never silently reset. Regression test asserts identical output for both orderings. |
| 6 | Two findings sharing an id (not reachable today given content-derived, analyzer-namespaced ids, but not actively prevented either) would silently overwrite one another in every `{f.id: f for f in findings}` call site in the CLI, dropping one finding with no error. | P3 | Fixed defensively: `_reject_duplicate_finding_ids` raises loudly instead of ever allowing a silent drop. |
| 7 | `test_run_bounded_respects_env` passed a single-key `env` to a Windows subprocess; `windows-latest`/Python 3.10 in CI failed to even start the interpreter (missing OS-required variables like `SystemRoot`). `process.py`'s full-replace `env=` semantics (matching `subprocess.Popen`) were correct; the test's assumption was not. | P3 (CI-only) | Fixed: test now overlays one variable onto a copy of the real environment, isolating "does the child see our variable" from "can this OS launch a process with almost no environment." Caught by the actual CI matrix, not local runs — confirms the matrix is doing real work. |

**Severity tally: P0 = 0, P1 = 0, P2 = 2 (fixed), P3 = 3 (fixed), P4 = 1
(fixed).** No P0/P1/P2 remain open.

Attack categories from the checklist that were exercised and found
already-safe (no fix needed): invalid config (unknown keys, bool-as-int,
NaN/Inf, out-of-bounds), corrupt JSON persistence (quarantined, not
repaired), missing files (`FileNotFoundError` propagates, never a fake
empty result), symlink/Windows-junction escape (rejected via
`paths.validate_contained`, never followed by the walker), huge directory
handling (file/depth/byte limits all independently tested), JSON stdout
purity (both in-process and via a real subprocess), non-determinism (same
input → identical output across repeated runs, asserted directly),
duplicate graph edges/dangling edges (rejected at insertion), priority ties
(deterministic id-based tie-break), hard-gate-overrides-good-score
(explicit regression test), minimum-meaningful-delta (explicit boundary
test), attempt-budget exhaustion and diminishing-returns detection (both
drive `KAIZEN_STABLE`), and output-budget truncation never dropping a
critical-severity finding (explicit 100-finding test with scattered
criticals).

## Known limitations

- **macOS is not verified.** CI covers Windows and Ubuntu only.
- Path containment is application-level defensive handling, not a kernel
  sandbox; a residual TOCTOU window exists between the pre-write
  containment check and the atomic replace (narrowed, not eliminated —
  documented in `persistence.py` and the README).
- Analyzer heuristics are small, regex/metadata-based checks; they will
  have false positives and false negatives (the version-mismatch heuristic
  in particular is explicitly labeled low-confidence in its own finding
  text).
- No LLM/semantic reasoning is used anywhere in v0.1.0 — every judgment is
  a deterministic, documented rule.
- v0.1.0 does not autonomously rewrite third-party source code; it
  analyzes, plans, compares, verifies (only via explicitly authorized
  commands), and records.
- Verification-command execution (`process.run_bounded`) is not a sandbox;
  it runs with the caller's own OS permissions. Untrusted projects need
  external isolation this tool does not provide.
- Nothing here guarantees every possible improvement is discovered.
- The CLI's `plan` command uses a documented, fixed heuristic mapping from
  finding severity/confidence to viability inputs (`_SEVERITY_BENEFIT`,
  `_HEURISTIC_EFFORT`, `_HEURISTIC_RISK` in `cli.py`) in the absence of a
  real root-cause/effort/risk assessment; it is a reasonable default for a
  first pass, not a substitute for human judgment on any individual
  improvement.

## Release state

- Version: `0.1.0`
- Tag: none
- GitHub Release: none
- PyPI: not published

## Status

**READY FOR FIRST INDEPENDENT ADVERSARIAL AUDIT.**
