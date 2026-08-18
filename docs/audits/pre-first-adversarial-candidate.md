# ProjectKaizen v0.1.0 — Pre-First-Adversarial-Audit Candidate

This document records the verified state of ProjectKaizen at the commit
below. It is a candidacy record, not a release: no tag, no GitHub Release,
no PyPI publish has been made.

This is the **second** version of this document. The first version
(against candidate `74b29c653dd13f14a1d3b7356aad6af2a167bead`) incorrectly
reported a single "302 passed, 0 skipped, 93.54% coverage" figure derived
only from a local Windows run, presented as if it applied everywhere. It
does not: 2 tests are Windows-junction-specific and are correctly skipped
on Linux, and Ubuntu's measured coverage differs slightly from Windows's.
This version reports platform-specific numbers explicitly and never
collapses them into one.

## Candidate

- Implementation SHA (v0.1.0 core — analyzers, CLI, tests): `0871455`
- Fix SHA (portable env test): `670d47f`
- First audit-doc SHA (superseded by this document): `74b29c6`
- **OSS-expansion implementation SHA:** `d650f27` (`d650f273765bd4043294cc51a8123fbbadb670c3`)
- **This document's commit will become the final candidate SHA** — see the
  FINAL STATUS section for the exact value once committed.
- Repository: https://github.com/Human-Weapon/ProjectKaizen
- Branch: `main`
- Version declared in `src/projectkaizen/_version.py`: `0.1.0`

## Recovery / continuity

Continued directly from the verified `74b29c6` state per this task's
explicit instruction not to restart. No existing module was rewritten
without technical cause; three real bugs found during this expansion's
self-adversarial pass were fixed at the root (see below) and everything
else from the prior candidate was preserved unchanged.

## OSS provenance

Full detail, exact commit SHAs, files read, and per-source classification
in [docs/oss-reuse-manifest.md](../oss-reuse-manifest.md) and
[THIRD_PARTY_NOTICES.md](../../THIRD_PARTY_NOTICES.md). Summary:

| Source | License | Mode |
|---|---|---|
| addyosmani/agent-skills | MIT | REFERENCE_ONLY |
| mattpocock/skills | MIT | REFERENCE_ONLY |
| obra/superpowers | MIT | REFERENCE_ONLY |
| massimodeluisa/recursive-decomposition-skill | MIT | REFERENCE_ONLY |
| openai/openai-agents-python | MIT | ADAPTED (tag resolution) + REFERENCE_ONLY (checklist) |
| chaunsin/agent-skills | Apache-2.0 | ADAPTED (category taxonomy only) |
| NeoLabHQ/context-engineering-kit | GPL-3.0 | REFERENCE_ONLY — no source read, no code copied |

All 7 licenses and commit SHAs were verified directly against the GitHub
API (`gh api repos/<owner>/<repo>`), not taken on trust. **No line of code
or substantial text was copied from any source into ProjectKaizen.**

## New capabilities in this expansion

- `root_cause/` — Five Whys, Fishbone, A3, PDCA, TraceBack as typed,
  validated containers for a root-cause investigation (not reasoning
  engines — ProjectKaizen has no LLM).
- `gates/fresh_evidence.py` — FRESH/STALE/UNBOUND/INSUFFICIENT; an
  improvement cannot ACCEPT on evidence bound to a different candidate,
  unbound, or only manually attested.
- `gates/preservation.py` — SAFE_TO_CHANGE/REQUIRES_MORE_CONTEXT/
  INTENT_STILL_VALID/DO_NOT_REMOVE; unknown evidence never reads as safe.
- `attempt_policy.py` — stop-the-line discipline on top of
  `models.AttemptBudget`: 3 failed attempts under an unchanged hypothesis
  requires new evidence, a changed hypothesis, or an explicit override.
- `analyzers/git_hotspots.py` — commit-frequency/recency ranking. Opt-in
  (not in the default `ALL_ANALYZERS` registry) since it is the one
  analyzer that runs a real subprocess.
- `analyzers/architecture_depth.py` — AST-based pass-through-function and
  shallow-wrapper-class detection; deliberately not an LOC-ratio metric.
- `blast_radius.py` — LOCAL/BOUNDED/CROSS_MODULE/CROSS_SYSTEM/UNKNOWN
  impact estimation, robust to import cycles (bounded BFS).
- `scale/decomposition.py` — inventory → filter → partition → analyze →
  merge → spot-check for large repositories; no LLM, no subagent.
- `release/` — scope resolution (never invents a baseline), offline tag
  resolution, base-vs-target diff/classification, public-contract
  comparison, an evidence-gated operational checklist, and readiness
  evaluation (BLOCKED/NEEDS_CONFIRMATION/NO_BLOCKER_FOUND — never "safe").
  New `projectkaizen release-readiness` CLI command plus a thin
  `skills/release-readiness/SKILL.md` wrapper with no duplicated logic.
- `human.py` — plain-language translation layer for the CLI's default
  text output (`plan`/`status`/`compare`/`release-readiness`), added in
  response to an explicit mid-task product requirement that ProjectKaizen
  require zero continuous-improvement methodology knowledge to use.
  `--full` still exposes the technical/internal view.

None of the new internal engines (root_cause strategies, the two gates,
blast radius) are wired into the default CLI flow — they are library
capabilities a caller can use, not something `inspect`/`plan`/`status`
force a user to configure.

## Tests

**Local (Windows, dev machine):** 426 passed, 0 skipped, 92.32% branch coverage

**CI — Windows (windows-latest), Python 3.10 / 3.11 / 3.12:** 426 passed, 0 skipped, each

**CI — Ubuntu (ubuntu-latest), Python 3.10 / 3.11 / 3.12:** 424 passed, 2 skipped, each
(the 2 skips are `test_windows_junction_detected_as_reparse_and_not_followed`
and `test_walk_does_not_follow_junction_escape` — junctions are a Windows-only
concept; both use `@pytest.mark.skipif(sys.platform != "win32", ...)`)

**CI — coverage-gate (ubuntu-latest, Python 3.12):** 424 passed, 2 skipped,
**92.09%** branch coverage (gate: ≥90%)

The Windows/Ubuntu pass-count difference (426 vs. 424) is exactly the 2
platform-gated skips — not a discrepancy, not flakiness.

### Notable real (non-mocked) regression coverage added this expansion

- real `git log`/`git tag`/`git diff`/`git show`/`git rev-parse` calls
  against real repositories built in `tmp_path` fixtures (`test_release.py`,
  `test_git_hotspots.py`, `test_cli_release_readiness.py`)
- a real annotated git tag, proving `git rev-parse` without `^{commit}`
  returns the wrong SHA and that the fix corrects it
  (`test_scope_annotated_tag_resolves_to_commit_sha_not_tag_object`)
- a 300-file synthetic repository decomposed, analyzed per-partition, and
  merged with a critical finding preserved and zero duplicate ids
- a real cyclic import pair proving blast-radius traversal terminates

## Quality gates

- Ruff lint (`src` + `tests`): clean
- Ruff format check: clean
- `git diff --check`: clean
- `git status`: clean at the candidate commit
- CI `ruff lint + format` job: green

## Build & packaging

- `python -m build`: wheel + sdist rebuilt after the OSS-expansion commit
- Wheel contents inspected: all new subpackages (`root_cause/`, `gates/`,
  `release/`, `scale/`, plus `attempt_policy.py`, `blast_radius.py`,
  `human.py`, `analyzers/git_hotspots.py`, `analyzers/architecture_depth.py`)
  present; still only `projectkaizen/*` + standard `dist-info` — no `.git`,
  caches, `.venv`, coverage artifacts, secrets, or sibling-project files
- CI `build wheel + sdist` job: green (includes an in-CI fresh-venv wheel
  smoke test)

## Black-box verification

Performed in fresh virtual environments outside the checkout:

- **Wheel**, Python 3.12: installs with zero dependencies beyond
  `projectkaizen` itself; `import projectkaizen` resolves to the installed
  `site-packages` copy (path-verified); every new module
  (`root_cause`, `gates.fresh_evidence`, `gates.preservation`,
  `attempt_policy`, `analyzers.git_hotspots`, `analyzers.architecture_depth`,
  `blast_radius`, `scale.decomposition`, `release`, `human`) imports
  successfully; `projectkaizen --version`/`--help` work.
- **Sdist**, Python 3.10: same checks, built from source under `uv`, pass.
- **Standalone check**: `pip list` in both fresh environments shows
  exactly one package — no PromptGraph, AgentGear, SkillGuard, AgentBench,
  or any of the 7 reviewed OSS sources present or required.

## Self-adversarial review (this expansion)

| # | Finding | Severity | Outcome |
|---|---|---|---|
| 1 | `git_hotspots` ranked committed generated/vendor files (e.g. a `dist/` bundle regenerated every commit) by raw commit count, letting machine churn drown out real source hotspots. | P3 | Fixed: `_is_generated_or_vendor_path` excludes `dist/build/vendor/target/out` (plus the existing walker ignore list) from ranking. Regression test proves a generated file never appears in results while the real source file does. |
| 2 | `release/scope.py` resolved an **annotated** git tag via plain `git rev-parse <tag>`, which returns the tag *object's* own SHA, not the commit it points to — confirmed with a real annotated tag (`a8bfc3e1...` vs. the actual commit `52c68295...`). `ReleaseRef.sha` would silently mean two different things depending on tag type. | P2 | Fixed at the root: `git rev-parse "<ref>^{commit}"` always dereferences to the real commit, verified against HEAD, `HEAD~1`, a plain SHA, a lightweight tag, an annotated tag, and a nonexistent ref (still fails cleanly). Regression test added. |
| 3 | `git_hotspots` treated a real, valid git repository with zero commits yet the same as a git failure (`ANALYSIS_INCOMPLETE`, reason: "git log failed: ..."), rather than the more honest `COMPLETE` with nothing to report — analogous to an empty directory walk. | P4 | Fixed: the specific "does not have any commits yet" stderr is now distinguished and reported as `COMPLETE`. |

**Severity tally this expansion: P0 = 0, P1 = 0, P2 = 1 (fixed), P3 = 1
(fixed), P4 = 1 (fixed).** Combined with the first candidate's pass
(2 P2, 3 P3, 1 P4, all fixed), **no P0/P1/P2 remain open anywhere in the
codebase.**

Attack categories from the expanded checklist (spec section 30) exercised
and found already-safe: cyclic dependency graph in blast radius (bounded
BFS terminates, regression-tested), decomposition duplicate findings
(id-based dedup), decomposition lost critical finding (explicit
regression test), release with no tags (never invents a baseline, tested),
malformed version tags (rejected by regex), dirty worktree contamination
(detected, forces NEEDS_CONFIRMATION), missing git executable (all three
new git-backed modules degrade honestly, never crash).

**Known, documented (not silently missing) gaps:**
- `release/checklist.py` does not detect queue/cache/external-service
  risk from a source diff alone (stated in its own module docstring) —
  those need infrastructure knowledge a text diff can't provide.
- HTML report mode and the test-pollution-probe port (both explicitly
  marked *optional* in the build spec) were not implemented this session,
  to protect time for the required OSS review, self-adversarial pass, and
  full verification. Not fabricated as done.

## Known limitations

Carried over from the first candidate, still accurate: macOS unverified
(CI covers Windows/Ubuntu only); path containment is application-level,
not a kernel sandbox; analyzer heuristics are small and will have false
positives/negatives; no LLM/semantic reasoning anywhere; not an autonomous
code rewriter; verification-command execution is not a sandbox; no
guarantee of exhaustive improvement discovery.

New to this expansion:
- `release/`'s base-vs-target contract comparison covers only the CLI
  subcommand set and `requires-python` — not a full public-API diff.
- `git_hotspots`/`release/` all shell out to `git`; if `git` is not on
  `PATH`, or the target is not a git repository, each degrades to an
  honest `FAILED`/`ANALYSIS_INCOMPLETE`/`NO_BASELINE` result rather than
  raising — but none of these modules function meaningfully without git.
- `blast_radius.py`'s consumer detection is import-text based (regex over
  `import`/`from` statements), not true name resolution — a false
  positive/negative is possible if a project uses dynamic imports.

## Release state

- Version: `0.1.0`
- Tag: none
- GitHub Release: none
- PyPI: not published

## FINAL STATUS

**READY FOR FIRST INDEPENDENT ADVERSARIAL AUDIT.**

(Final candidate SHA: the commit that adds this document — see the
implementation report for its exact value; `origin/main` matches it.)
