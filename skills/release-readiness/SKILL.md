---
name: release-readiness
description: Check whether a target ref is safe to release relative to a base, using ProjectKaizen's release-readiness command. Use when the user asks "is this ready to ship", wants a pre-release check, or asks to compare a release baseline against the current state.
---

# Release Readiness

This skill is a thin wrapper. It does not reimplement anything — the
Python package (`projectkaizen.release`) is the source of truth. Your job
is to run the command and interpret its structured output for the user,
not to re-derive the analysis yourself.

## Running it

```bash
projectkaizen release-readiness <path> [--base REF] [--target REF] [--json]
```

- `<path>` — the repository to check (defaults to `.`).
- `--base` — explicit base ref to compare from. If omitted, ProjectKaizen
  looks for the latest version-like git tag; if none exists, it reports
  `NO_BASELINE` rather than guessing one.
- `--target` — explicit target ref (defaults to `HEAD`).
- `--json` — pure JSON on stdout for programmatic use; prefer this when
  you (the agent) are the consumer.

## Interpreting the output

The `outcome` field is one of three values — treat them literally, don't
round up:

- `blocked` — a hard compatibility break was found (e.g. a CLI subcommand
  was removed). Surface this to the user before proceeding with a release.
- `needs_confirmation` — real, diff-driven signals exist (schema/config/
  dependency/CLI/public-API changes, or an uncommitted worktree) that a
  human needs to confirm are handled. This is **not** a defect list — it's
  a "go check these specific things" list. Read each finding's
  `description` and `affected_paths` and relay them concretely.
- `no_blocker_found` — nothing in ProjectKaizen's checks raised a concern.
  **Do not describe this as "safe to release" or "verified safe."** It
  means exactly what it says: no blocker was found by these specific,
  limited checks. Say that, not more.

Also check `scope.confidence`:
- `no_baseline` means there was nothing to diff against at all — the
  `findings` list will be empty and `outcome` will be `needs_confirmation`
  for that reason alone. Tell the user to provide `--base` explicitly.

## What this skill will not do

- It will not tell you the release is "guaranteed safe" — no output of
  this command should ever be paraphrased that way.
- It will not check runtime infrastructure (queues, caches, external
  services) unless a changed file's *name* hints at it — this is a static,
  offline check, not a deployment audit.
- It will not perform the release, tag anything, or push. That remains a
  separate, explicitly authorized action.
