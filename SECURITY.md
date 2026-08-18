# Security Policy for ProjectKaizen

## Reporting a vulnerability

If you discover a potential vulnerability, avoid posting sensitive exploit
details publicly. Open a minimal issue requesting a private reporting channel,
or use GitHub Private Vulnerability Reporting if it is enabled for this
repository.

Please include:

- a description of the issue
- steps to reproduce
- affected versions
- any suggested fix

There is no dedicated security email for this project.

## Threat model (be precise)

- **Static inspection never executes the target project.** Analyzers walk
  the project tree, read text, and parse `pyproject.toml`'s dependency list
  with plain text handling — they never import the target package, run its
  build backend, or install anything.
- **Verification commands are explicit `argv` sequences, `shell=False`.**
  ProjectKaizen only runs a verification command when a caller supplies one
  via a `VerificationPlan`; it never discovers and auto-runs arbitrary
  project scripts. Commands run with an explicit timeout and bounded
  captured output.
- **Dynamic command execution is not a sandbox.** A verification command
  runs with the caller's own OS permissions. Untrusted projects need
  external isolation (a container, VM, or throwaway user account) — this
  tool does not provide one.
- **Path containment is defensive, application-level best effort**, not a
  kernel sandbox: symlinks and Windows junctions are detected and not
  followed, and every write target is re-validated immediately before the
  atomic replace. This narrows, but does not eliminate, TOCTOU races against
  a concurrent hostile actor with write access to the same filesystem.
- **No network calls, no telemetry, no LLM calls, no API keys** are required
  or used by any core functionality.
- Persisted state under `.agentops/kaizen/` uses atomic writes with a schema
  envelope; corrupt state is quarantined, never silently repaired or trusted.
- ProjectKaizen does **not** perform deep security auditing, dynamic
  behavior analysis, or capability/containment verification of skills or
  plugins. That job belongs to **SkillGuard**. ProjectKaizen's own static
  checks (e.g. flagging `subprocess(shell=True)` or `eval`/`exec`) are
  lightweight signals for its own improvement findings, not a security
  audit of your project.

## What ProjectKaizen deliberately does NOT do

- context compilation, requirement extraction, or token budgeting (PromptGraph)
- model routing, reasoning-effort selection, or agent orchestration (AgentGear)
- deep security auditing or dynamic behavior analysis of skills/plugins (SkillGuard)
- running benchmarks or measuring agent/model performance (AgentBench)
- autonomously rewriting third-party source code

## Standalone guarantee

ProjectKaizen must never require a sibling package to function. `import projectkaizen`
and the CLI work completely standalone, offline, with no API keys and no network access.

## Priority

- **P0** — security / data loss / critical bugs: fix immediately
- **P1** — broken functionality: next release
- **P2+** — scheduled normally
