# Contributing to ProjectKaizen

Thanks for considering contributing. ProjectKaizen is part of the HERMES OSS ecosystem. By participating you agree to: **USEFUL ALONE + BETTER TOGETHER**, evidence over confidence, and no analysis without decision value.

## Before you start

- **SEARCH before you create** — check whether the feature already exists or belongs in a sibling (PromptGraph, AgentGear, SkillGuard, AgentBench). ProjectKaizen's job is **finding, prioritizing, verifying, and recording evidence-based improvements** — not context compilation, model routing, security auditing, or benchmarking.
- **EXTEND before you duplicate** — improve an existing analyzer or engine instead of adding an overlapping one.
- New optional analysis engines must respect **"no analysis without decision value"**: they must not run unless `method_selection.select_method()` (or an equivalent, explicit caller decision) actually calls for them, and they must never be wired into the default CLI flow without a real reason. See `tests/test_engines_stay_conditional.py` for the enforcement pattern.
- Do not add an LLM call, an API key requirement, telemetry, or network access anywhere in the core package.

## Development setup

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

## Quality checks

```bash
pytest
ruff check src/ tests/
ruff format src/ tests/
python -m build
```

Coverage must stay at or above the `--cov-fail-under=90` branch-coverage gate configured in `pyproject.toml`.

## Commit conventions

Small, focused commits with conventional prefixes:

`feat:`, `fix:`, `test:`, `docs:`, `refactor:`, `perf:`, `security:`, `chore:`

Never commit secrets. Run `git diff` + `ruff` + `pytest` before committing.

## Standards

- No telemetry and no phone-home. No network access, no LLM calls, no API keys required for any core functionality.
- Standalone by default. Optional sibling integration must degrade gracefully if the sibling isn't installed.
- Evidence over confidence. A `Finding` needs real `Evidence`, not a free-text guess. A statistical conclusion must check effect size (`minimum_meaningful_delta`) before claiming significance means anything.
- Hard gates always win. No averaged score may compensate for a broken required behavior, broken critical test, security regression, or data loss.
- Verification commands stay explicit `argv` sequences with `shell=False`. Never auto-discover and run arbitrary project scripts.
- Default CLI output stays plain-language and assumes zero Kaizen/Lean/Six Sigma/PDCA/root-cause-analysis vocabulary. `--full`/`--explain` may expose internal method names; the default view never should.
- `pytest` + `ruff check` must be green before merge.
- Critical defects need a regression test that fails on the broken behavior and passes on the fix.
