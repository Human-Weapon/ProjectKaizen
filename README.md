# ProjectKaizen

Continuous-improvement toolkit for software and AI-agent projects: finds,
prioritizes, verifies, and records evidence-based improvements.

ProjectKaizen answers: **what should improve next, why, how do we verify it
got better, and when is further improvement no longer worth the cost?**

## What it does

- Walks a project (safely, bounded, without executing any of its code) and
  runs small, deterministic, explainable analyzers over it.
- Turns what it finds into structured `Finding`s with severity, confidence,
  and evidence — not free-text guesses.
- Gates every potential improvement through an explicit **viability**
  check (`VIABLE` / `MARGINAL` / `NOT_WORTH_IT` / `DEFER` /
  `INSUFFICIENT_EVIDENCE`) before it's ever treated as actionable. The
  existence of a possible improvement does not imply implementing it is
  worthwhile.
- Compares a real baseline against a real candidate, never against an
  abstract idea of "perfect code". A **hard gate** violation (broken
  required functionality, broken critical tests, security regression, data
  loss, broken promised compatibility, exceeded budget, platform violation,
  removed required behavior) always rejects the candidate — no averaged
  score can compensate for it.
- Enforces a **minimum meaningful delta** per metric, so a 0.1ms
  "improvement" against a 5ms threshold is correctly treated as noise, not
  progress.
- Detects **diminishing returns** and enforces an **attempt budget**, so
  improvement work doesn't loop forever chasing fractional gains.
- Can conclude **KAIZEN_STABLE**: "no currently worthwhile evidence-backed
  improvement remains" — never "the software is perfect".
- Keeps a bounded, deterministic **history**: problem → evidence → root
  cause → failed attempts → decision → solution → regression test → result
  → lesson.
- Defaults to **concise output**. Large result sets are summarized
  ("37 findings detected; showing top 5"), but critical-severity findings
  are never silently dropped by truncation, and `--full` always exposes
  everything the concise view was derived from.

## What it does NOT do

ProjectKaizen is one of five independent tools in the HERMES OSS collection
(*useful alone, better together* — see "Ecosystem" below) and deliberately
does not duplicate its neighbors:

- It does not compile agent context, extract requirements, or manage a
  context graph/token budget (that's **PromptGraph**).
- It does not choose models, reasoning effort, or orchestrate agents
  (that's **AgentGear**).
- It does not perform deep security auditing, dynamic behavior analysis, or
  containment verification of skills/plugins (that's **SkillGuard**). It
  only does lightweight structural checks (e.g. `subprocess(shell=True)`,
  `eval`/`exec`, obvious plaintext-secret filenames).
- It does not run benchmarks or measure agent/model performance (that's
  **AgentBench**); it consumes baseline/candidate metrics as plain numbers,
  wherever they came from.
- It does not autonomously rewrite third-party source code. v0.1.0 can
  analyze, propose, plan, compare, verify (via explicitly authorized
  commands), and record — it does not patch your project for you.

None of the above are required dependencies. `import projectkaizen` and the
CLI work completely standalone, offline, with no API keys, no LLM calls, and
no network access.

## Ecosystem

ProjectKaizen is part of the HERMES OSS collection (**useful alone, better
together**): [PromptGraph](https://github.com/Human-Weapon/PromptGraph)
(context compilation), [AgentGear](https://github.com/Human-Weapon/AgentGear)
(execution routing), [SkillGuard](https://github.com/Human-Weapon/SkillGuard)
(security/behavior auditing), [AgentBench](https://github.com/Human-Weapon/AgentBench)
(benchmarking), **ProjectKaizen** (continuous improvement — this project).

> **About HERMES OSS:** HERMES OSS is the name used for this collection of
> five independent open-source tools. There is no separate HERMES package,
> private runner, hidden orchestrator, or required sixth component. Each
> tool works standalone. "Better together" means the optional interoperability
> below, not a required central runtime or an automated five-tool pipeline.

| Relationship | Status | Notes |
|---|---|---|
| AgentBench → ProjectKaizen | Manual / data-level | `compare`/`baseline` accept plain baseline/candidate metric numbers from any source, including an AgentBench `summary.json`/`comparison.json` you point at explicitly. There is no automatic adapter. |
| PromptGraph / AgentGear / SkillGuard | Not integrated | ProjectKaizen does not read from or write to these tools. |
| Full five-tool pipeline | Not provided | No `hermes run`/`hermes orchestrate` or equivalent central runner exists. |

ProjectKaizen has no hard dependency on any sibling; it consumes plain
baseline/candidate metrics and evidence from wherever they came from, and
degrades gracefully if a sibling isn't installed.

> **Note:** ProjectKaizen v0.1.0 is a release candidate awaiting its first
> independent adversarial audit — see [`docs/audits/`](docs/audits/). No git
> tag, GitHub Release, or PyPI publish has been made yet.

## Installation

```bash
pip install projectkaizen
```

or, from a checkout:

```bash
pip install -e ".[dev]"
```

## Quick start

```bash
projectkaizen inspect .        # run analyzers, show top findings (concise)
projectkaizen findings . --full  # same analysis, full evidence, no truncation
projectkaizen plan .           # findings that clear the viability gate
projectkaizen baseline . --id b1 --metric latency_ms=100
projectkaizen compare baseline.json candidate.json
projectkaizen status .         # is this project KAIZEN_STABLE right now?
projectkaizen history .        # bounded, deterministic improvement history
projectkaizen validate config.json
```

Add `--json` to any command for pure, deterministic JSON on stdout (nothing
else is written to stdout in `--json` mode). See `docs/sample_project/` for
a small fixture you can run all of the above against directly.

## Exit codes

| Code | Meaning |
|------|---------|
| 0 | success, nothing requires attention |
| 1 | actionable findings exist / comparison REJECTed / not KAIZEN_STABLE |
| 2 | invalid input, config, or arguments |
| 3 | analysis incomplete, or comparison INCONCLUSIVE/DEFERred |
| 4 | persisted state is corrupt |
| 5 | a verification command failed or timed out |
| 6 | a path escaped its trusted root |

## The ImprovementGraph

Findings, root causes, improvements, evidence, outcomes, and lessons are
nodes in an explicit `ImprovementGraph` (`projectkaizen.graph`) with typed
edges (`AFFECTS`, `CAUSED_BY`, `IMPROVED_BY`, `DEPENDS_ON`, `VALIDATED_BY`,
`CONFLICTS_WITH`, `SUPERSEDES`, `RESULTED_IN`, `LEARNED_FROM`). Node/edge
ids are deterministic (content-derived, never random or timestamp-based),
edges can never dangle (enforced at insertion, not just at validation time),
and dependency cycles are detected explicitly rather than crashing.

## `.agentops/kaizen/`

ProjectKaizen optionally persists artifacts under `.agentops/kaizen/` inside
the inspected project (`inspect --persist`, `baseline`, `compare --record`).
`.agentops/` is a shared directory *convention*, not a central HERMES
service or database — each tool owns and validates only its own
subdirectory. ProjectKaizen reads only its own `kaizen/` subdirectory and
fails cleanly (never silently) if it's absent or corrupt.

## Security model and limitations

- **Static inspection never executes the target project.** It parses text
  and `pyproject.toml`'s dependency list with plain regex, not `tomllib`
  (kept off the dependency list; also `tomllib` is 3.11+ only and this
  project supports 3.10) — it never imports the target package, runs its
  build backend, or installs anything.
- **Verification commands are explicit `argv` sequences, `shell=False`.**
  ProjectKaizen only runs a verification command when a caller supplies one
  via a `VerificationPlan`; it never discovers and auto-runs arbitrary
  project scripts.
- **Dynamic command execution is not a sandbox.** A verification command
  runs with the caller's own OS permissions. Untrusted projects need
  external isolation (a container, VM, or throwaway user account) — this
  tool does not provide one.
- **Path containment is defensive, application-level best effort**, not a
  kernel sandbox: symlinks and Windows junctions are detected and not
  followed, and every write target is re-validated immediately before the
  atomic replace. This narrows, but does not eliminate, TOCTOU races against
  a concurrent hostile actor with write access to the same filesystem.
- **No network, no telemetry, no LLM, no API keys required** for any core
  functionality.
- Analyzer heuristics are small and regex/metadata-based; they will have
  false positives and false negatives. They are not a substitute for a
  linter, a security scanner, or human review.
- macOS is **not verified** — CI runs Windows and Ubuntu only.
- v0.1.0 does not autonomously rewrite arbitrary source code.
- Nothing here guarantees every possible improvement is discovered, or that
  accepted improvements are risk-free.

## License

MIT — see [LICENSE](LICENSE).
