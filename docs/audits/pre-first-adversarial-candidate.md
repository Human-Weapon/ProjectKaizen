# ProjectKaizen v0.1.0 — Pre-First-Adversarial-Audit Candidate

This document records the verified state of ProjectKaizen at the commit
below. It is a candidacy record, not a release: no tag, no GitHub Release,
no PyPI publish has been made.

This is the **third** version of this document.
- v1 (against `74b29c6`) incorrectly reported a single "302 passed, 0
  skipped, 93.54%" figure from a local Windows run only, applied
  everywhere. Superseded.
- v2 (against `6f211bf`) fixed that by reporting explicit per-platform
  numbers and added the OSS-assisted capability expansion (root_cause/,
  gates/, git_hotspots, architecture_depth, blast_radius,
  scale/decomposition, release/).
- **v3 (this version)** adds the method-selection governance layer and
  the statistics package, and reports fresh evidence against the new
  candidate. Per-platform reporting is preserved.

## Candidate history

| SHA | What it is |
|---|---|
| `4fa46bd` | prior-session checkpoint (6 primitive modules only) |
| `0871455` | v0.1.0 core (models, graph, analyzers, CLI, tests) |
| `670d47f` | portable-env test fix |
| `74b29c6` | v1 audit doc (superseded) |
| `d650f27` | OSS-assisted capability expansion implementation |
| `6f211bf` | v2 audit doc (superseded) |
| **`809c2a1`** | method-selection + statistics implementation |
| **this commit** | v3 audit doc — **final candidate SHA** |

Repository: https://github.com/Human-Weapon/ProjectKaizen · Branch: `main`
· Declared version: `0.1.0`

## What this version adds

**`method_selection.py`** — the explicit governance layer the build spec
requires above every optional analysis engine. Core rule: *no analysis
without decision value*. `select_method()` stops immediately if existing
evidence is already sufficient (nothing runs, not even the cheapest
option); otherwise it picks the lowest-tier, lowest-cost candidate from a
fixed preference order — direct evidence < deterministic rule <
statistical < causal investigation < bounded experiment.
`sufficiency_from_hard_gate_violations()` gives "no statistics when
obvious" (a failed test, missing file, removed contract, incompatible
schema already decides the outcome) a reusable, tested form. Statistical
methods and continuous-improvement methodology (root_cause/) are peers in
this ordering — neither is privileged; the cheaper tier wins.

**`statistics/`** — descriptive stats, a percentile-bootstrap confidence
interval, a nonparametric permutation test, and Cohen's d effect size,
combined by `evaluate_difference()` into one `StatisticalConclusion`.
Reliability comes from the bootstrap CI excluding zero (not a bare
p<0.05), then gated by `minimum_meaningful_delta` before ever being called
"meaningful" — effect size before significance, matching the build spec's
own example (a statistically real 0.2% speedup against a 5% minimum delta
is `RELIABLE_BUT_TOO_SMALL`, not actionable). Every resampling function
requires an explicit `seed` — the one place ProjectKaizen intentionally
uses randomness, done openly and reproducibly rather than pretending
determinism where it isn't the right tool. Deliberately does *not*
implement CUSUM/EWMA/change-point detection/causal inference — these were
named as *possibilities* in the spec, not requirements, and each needs
real validation work beyond what a single session should rush.

**`human.py` additions** — plain-language translations for fresh-evidence,
blast-radius, preservation, attempt-guidance, and root-cause-strategy
results (e.g. "Likely cause" regardless of whether Five Whys or Fishbone
produced it), so these engines are UX-ready without ever requiring
methodology knowledge, per the standing zero-continuous-improvement-
knowledge product requirement.

None of the 7 optional engines (`git_hotspots`, `blast_radius`,
`preservation_gate`, `root_cause_strategy`, `statistical_strategy`,
`release_readiness`, `repository_decomposer`) are wired into the default
CLI flow — verified by a real subprocess check
(`tests/test_engines_stay_conditional.py`) that `inspect` and
`release-readiness` never load unrelated engine modules.

## Tests

**Local (Windows, dev machine):** 480 passed, 0 skipped, 92.27% branch coverage

**CI — Windows (windows-latest), Python 3.10 / 3.11 / 3.12:** 480 passed, 0 skipped, each

**CI — Ubuntu (ubuntu-latest), Python 3.10 / 3.11 / 3.12:** 478 passed, 2 skipped, each
(same 2 Windows-junction-only tests as every prior version)

**CI — coverage-gate (ubuntu-latest, Python 3.12):** 478 passed, 2 skipped, **92.06%** branch coverage (gate: ≥90%)

CI run: https://github.com/Human-Weapon/ProjectKaizen/actions/runs/32185634183
(all 9 jobs green: 6-way OS×Python matrix, coverage-gate, ruff lint+format, build)

### Notable new regression coverage

- a real Type-I-error sanity check for the permutation test (60 trials of
  identical-distribution samples, false-positive rate checked against the
  nominal ~5%)
- exact-vs-Monte-Carlo permutation test paths both exercised and cross-
  checked against hand-computed probabilities for small samples
- reproducibility proofs (same seed → byte-identical `ConfidenceInterval`/
  `PermutationTestResult`/`StatisticalConclusion`) for every randomized function
- a real fresh-subprocess check that optional engines never load unless
  the command that needs them is actually invoked

## Self-adversarial review (this version)

| # | Finding | Severity | Outcome |
|---|---|---|---|
| 1 | Passing NaN/Inf sample data into any statistics function crashed with a confusing internal `AttributeError` from stdlib `statistics.stdev` (Python 3.11+'s exact-fraction arithmetic has no path for NaN) instead of a clean `ValidationError`. | P2 | Fixed: every public entry point (`compute_descriptive_stats`, both bootstrap functions, `permutation_test`, `cohens_d`) validates every sample value is finite before any computation runs (`statistics/_validate.py`). Regression tests added for each. |
| 2 | `human.py`'s top-level imports of `blast_radius`/`gates.*`/`attempt_policy`/`root_cause` caused `cli.py` to transitively load every optional engine for *every* command, even ones that never touch those concepts — exactly the "unused engine execution" the spec prohibits. Caught by a real fresh-subprocess test, not inspection. | P2 | Fixed: those imports moved to be lazy (function-local, `TYPE_CHECKING`-guarded for type hints). Verified via `tests/test_engines_stay_conditional.py` running `inspect` and `release-readiness` in fresh subprocesses and checking `sys.modules`. |

Combined with the prior two candidacy rounds (2 P2 + 3 P3 + 1 P4, then 1
P2 + 1 P3 + 1 P4, all fixed), **no P0/P1/P2 finding remains open anywhere
in the codebase.**

Other attack angles from the expanded checklist exercised and found
already-safe: `select_method` with zero candidates offered (returns
"needs more evidence, nothing to suggest" rather than crashing or
inventing an option); `MethodSelection`'s own invariant (a "stop" state
can never carry a chosen method; a "continue" state legitimately can carry
none); degenerate statistics inputs (all-identical values, zero pooled
variance in Cohen's d) confirmed to return well-defined, non-crashing
results rather than division errors.

## Quality gates

Ruff lint + format: clean (including the new `tests/**` `S311` per-file
exception for legitimate, explicitly-seeded statistical resampling in test
fixtures). `git diff --check`: clean. `git status`: clean at the candidate
commit. CI `ruff lint + format` job: green.

## Build & black-box

`python -m build` rebuilt after this commit; wheel/sdist inspected —
`statistics/` and `method_selection.py` present, still only
`projectkaizen/*` + standard `dist-info`, no junk. Fresh Python 3.12
venv outside the checkout: wheel installs with zero dependencies,
`from projectkaizen.statistics import evaluate_difference` and
`from projectkaizen.method_selection import select_method` both work from
the installed `site-packages` copy, a real two-sample evaluation runs
correctly. `pip list` shows exactly one package.

## Known limitations

Carried over from prior versions (macOS unverified, application-level
path containment, analyzer heuristics have false positives/negatives, no
LLM/semantic reasoning, not an autonomous rewriter, verification execution
is not a sandbox). New this version:

- `statistics/` implements 4 methods (descriptive stats, bootstrap CI,
  permutation test, Cohen's d) out of the larger list of *possibilities*
  named in the build spec (CUSUM/EWMA, change-point detection, sequential
  analysis, causal inference, robust outlier-resistant estimators beyond
  median/MAD). This is a deliberate scope decision, stated in the
  package's own docstring, not a gap discovered later.
- `method_selection.py`'s `AnalysisCost.estimated_cost` is a documented,
  transparent weighted sum, not a calibrated prediction — it orders
  candidates sensibly but its absolute units aren't meaningful outside
  that ordering.
- Bootstrap/permutation reproducibility is guaranteed only for identical
  Python's `random.Random` behavior; this ties the exact numeric output
  (not the qualitative conclusion) to CPython's PRNG implementation.

## Release state

Version: `0.1.0` · Tag: none · GitHub Release: none · PyPI: not published

## FINAL STATUS

**READY FOR FIRST INDEPENDENT ADVERSARIAL AUDIT.**
