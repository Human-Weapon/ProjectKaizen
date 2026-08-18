# OSS Reuse Manifest

Every external source considered for this expansion, verified directly
against the live GitHub API (license, default branch, exact commit SHA) —
not taken on trust from any secondhand description. Verified 2026-08-18.

Reuse modes: **DIRECT** (code copied verbatim), **ADAPTED** (structure/
approach carried over, reimplemented independently), **PORTED** (behavior
translated to a new language, logic-for-logic), **CLEAN_ROOM** (built from
a general, non-proprietary concept without reading the source's
implementation), **REFERENCE_ONLY** (repo/concept reviewed, nothing
copied or structurally carried over).

No source in this manifest was classified as **DIRECT**. No line of code
or substantial text was copied from any of them into ProjectKaizen.

---

## 1. Addy Osmani — agent-skills

- **Repository:** https://github.com/addyosmani/agent-skills
- **License:** MIT (confirmed via `gh api repos/addyosmani/agent-skills` → `license.spdx_id`)
- **Commit verified:** `df1edb2e05487d0aa6d93c747141e0aed1187f25` (`main`)
- **Reuse mode:** REFERENCE_ONLY
- **What was reviewed:** repository existence, license, and top-level
  structure (`skills/`, `agents/`, `docs/`, etc.) confirmed via the GitHub
  contents API. Individual skill file contents were not fetched.
- **What ProjectKaizen target file(s) this informed:** `gates/preservation.py`
- **What was reused:** the general idea that "not understanding why code
  exists is not evidence it's unnecessary" (Chesterton's-Fence-style
  preservation reasoning) and that simplification should be
  behavior-preserving — both attributed here as concepts, not text.
- **What was changed / independently built:** the entire
  `PreservationEvidence`/`PreservationDecision` model, its four-outcome
  contract (SAFE_TO_CHANGE/REQUIRES_MORE_CONTEXT/INTENT_STILL_VALID/
  DO_NOT_REMOVE), and its deterministic rule evaluation are original to
  ProjectKaizen and match its own frozen-dataclass/enum contract style.
- **Attribution requirement:** none beyond this record (MIT, no code copied).
- **Tests covering the port:** N/A (no port) — `tests/test_gates.py`
  covers the independently-built preservation gate.

## 2. Matt Pocock — skills

- **Repository:** https://github.com/mattpocock/skills
- **License:** MIT (confirmed via GitHub API)
- **Commit verified:** `9c9f36ccd3995266cd675468af71639c8dde1ec5` (`main`)
- **Reuse mode:** REFERENCE_ONLY
- **What was reviewed:** repository existence, license, top-level structure
  (`skills/`, `docs/`, `.agents/`). Individual skill file contents were not
  fetched.
- **What ProjectKaizen target file(s) this informed:** `analyzers/architecture_depth.py`
- **What was reused:** module-depth vocabulary (module / interface burden
  / seam / adapter / leverage / locality), which itself originates from
  John Ousterhout's *A Philosophy of Software Design* and is not
  proprietary to this repository — used here as terminology, not text.
  The build spec explicitly warned against implementing depth as an
  implementation-LOC/interface-LOC ratio; `architecture_depth.py` follows
  that warning and uses AST-based pass-through/wrapper detection instead.
- **What was changed / independently built:** the entire detector
  (`_is_passthrough_function`, `_find_shallow_wrapper_classes`) is original
  Python using the stdlib `ast` module, with its own thresholds
  (`MIN_PASSTHROUGH_FUNCTIONS`, `WRAPPER_DELEGATION_RATIO`) and confidence
  capping (never above MEDIUM).
- **Attribution requirement:** none beyond this record (MIT, no code copied).
- **Tests covering the port:** N/A — `tests/test_architecture_depth.py`
  covers the independently-built analyzer.

## 3. obra — Superpowers

- **Repository:** https://github.com/obra/superpowers
- **License:** MIT (confirmed via GitHub API)
- **Commit verified:** `b36e0829c6d0140e93cfef2ca599b1b07d4a7797` (`main`)
- **Reuse mode:** REFERENCE_ONLY
- **What was reviewed:** repository existence, license, top-level structure
  (`skills/`, `hooks/`, `docs/`). Individual skill file contents were not
  fetched.
- **What ProjectKaizen target file(s) this informed:** `gates/fresh_evidence.py`, `attempt_policy.py`
- **What was reused:** two concepts — "verification evidence must be about
  the exact candidate being judged, not a prior one" (fresh evidence
  before completion claims), and "after repeated failures under the same
  hypothesis, stop and reconsider the approach rather than trying fix #4"
  (stop-the-line debugging discipline). Both are described generically in
  the build spec itself (sections 9 and 12) and implemented independently.
- **What was changed / independently built:** `CandidateIdentity` /
  `VerificationEvidence` / `EvidenceFreshness` (FRESH/STALE/UNBOUND/
  INSUFFICIENT) in `fresh_evidence.py`, and the attempt-count thresholds
  plus `AttemptGuidance` state machine in `attempt_policy.py`, are original
  Python built on ProjectKaizen's existing `models.AttemptBudget` — no
  shell, no markdown-skill structure, no code from the source repo.
- **Attribution requirement:** none beyond this record (MIT, no code copied).
- **Tests covering the port:** N/A — `tests/test_gates.py`,
  `tests/test_attempt_policy.py`.

## 4. Recursive Decomposition Skill

- **Repository:** https://github.com/massimodeluisa/recursive-decomposition-skill
- **License:** MIT (confirmed via GitHub API)
- **Commit verified:** `1780d46a73e485cbad4d0a48c019475d8be9193e` (`main`)
- **Reuse mode:** REFERENCE_ONLY
- **What was reviewed:** repository existence, license, top-level structure
  (`plugins/`, `assets/`). Individual file contents were not fetched.
- **What ProjectKaizen target file(s) this informed:** `scale/decomposition.py`
- **What was reused:** the six-stage pipeline shape named in the build
  spec — inventory → filter → partition → analyze → aggregate →
  spot-check — carried over as the module's function names
  (`inventory`/`filter_files`/`partition_by_*`/`analyze_partition`/
  `merge_results`/`verify_sample`).
- **What was changed / independently built:** every function body —
  deterministic bin-packing by directory or byte size, content-derived
  partition ids via `fingerprint.deterministic_id`, FIFO-safe merge with
  id-based deduplication, and evenly-spaced deterministic sampling (no
  randomness) — is original to ProjectKaizen. Explicitly, per spec section
  13, no subagent orchestration or LLM call was added; this module only
  defines the units.
- **Attribution requirement:** none beyond this record (MIT, no code copied).
- **Tests covering the port:** N/A — `tests/test_scale_decomposition.py`,
  including a 300-file synthetic-repository end-to-end test.

## 5. OpenAI Agents Python

- **Repository:** https://github.com/openai/openai-agents-python
- **License:** MIT (confirmed via GitHub API)
- **Commit verified:** `ebb746dc00b0dd6a90c30bc5ccb7e9c445e55493` (`main`)
- **Reuse mode:** ADAPTED (tag resolution) + REFERENCE_ONLY (checklist structure)
- **Source files read in full:**
  - `.agents/skills/final-release-review/scripts/find_latest_release_tag.sh`
  - `.agents/skills/final-release-review/references/review-checklist.md`
  (both confirmed present at the exact paths named in the build spec)
- **What ProjectKaizen target file(s) this informed:** `release/tags.py`, `release/checklist.py`, `release/diff.py`

### 5a. `find_latest_release_tag.sh` → `release/tags.py` (ADAPTED)

The source script: `git fetch <remote> --tags --prune` (network access),
then `git tag -l <pattern> --sort=-v:refname | head -n1` to pick the
highest version tag by git's own version-aware sort, erroring if none
match.

`release/tags.py`'s `resolve_latest_tag`/`list_tags`/`parse_version_tag`
carry over the *behavior* (list tags, find the highest version-like one,
return `None`/error honestly if none exist) but are not a line-for-line
port:

- **No network fetch.** ProjectKaizen core is offline-first (build spec
  section 26); `list_tags` only ever reads local tags via
  `git tag --list`. Fetching remote tags is not implemented anywhere in
  this codebase.
- **Own version parsing**, not git's `--sort=-v:refname`: `parse_version_tag`
  is a Python regex (`^v?(\d+)\.(\d+)\.(\d+)`) producing a comparable
  tuple, sorted in Python.
- **No glob pattern parameter** — the source takes a `pattern` arg
  (default `v*`); ProjectKaizen filters purely by whether a tag parses as
  `X.Y.Z`.

### 5b. `review-checklist.md` → `release/checklist.py`, `release/diff.py` (REFERENCE_ONLY)

Read in full. It is written specifically for the `openai-agents-python`
SDK's own domain (Runner/RunState, tool execution, sessions, provider
adapters) and is not a generic checklist — no text or structure from it
was carried into ProjectKaizen. `release/diff.py`'s `ChangeCategory`
enum (PUBLIC_API, PERSISTED_SCHEMA, PACKAGE_METADATA, ...) was designed
independently against the build spec's own section 17 list, and happens
to overlap conceptually with this file's "Public API / Persisted
schemas/config / Package boundary" table rows — because both are
describing the same general release-review problem, not because either
copied the other.

- **Attribution requirement:** MIT — none beyond this record.
- **Tests covering the port:** `tests/test_release.py::test_resolve_latest_tag_picks_highest_version`,
  `test_list_tags_empty_repo`, `test_resolve_latest_tag_none_when_no_tags`.

## 6. chaunsin — agent-skills

- **Repository:** https://github.com/chaunsin/agent-skills
- **License:** Apache-2.0 (confirmed via GitHub API)
- **Commit verified:** `faebdfcb7a66e327b8997a99022903225ba61830` (`master`)
- **Source file read in full:** `skills/pre-release-review/references/checklist.md`
- **Reuse mode:** ADAPTED (category taxonomy only)
- **What ProjectKaizen target file(s) this informed:** `release/models.py` (`ChangeCategory`), `release/checklist.py`
- **What was reused:** the checklist's *category structure* — it organizes
  release risk into Database/data, Environment/config, Security, Cache/CDN,
  Queues/events, External services, Deploy order, CI/CD, Observability.
  `release/checklist.py`'s docstring explicitly acknowledges this
  structure and its own narrower scope.
- **What was changed / independently built:** ProjectKaizen implements
  only a subset — config/env, persisted-schema/migrations, dependencies,
  CLI/API/compatibility, and build artifacts — using its own
  `ChangeCategory` enum values and 100% original guidance text
  (`_CATEGORY_GUIDANCE` in `checklist.py`). No bullet point, sentence, or
  phrase from the source file appears in ProjectKaizen. Queue contracts,
  cache invalidation, CDN/asset provisioning, and security/secret-material
  categories from the source checklist are **not** implemented — this is
  stated as an explicit, honest limitation in `checklist.py`'s module
  docstring rather than silently claimed as covered.
- **Apache-2.0 attribution:** the source repository's root contains no
  separate `NOTICE` file (confirmed via directory listing — only
  `LICENSE`, `README.md`, `README_CN.md`, `AGENTS.md`, `CLAUDE.md` exist),
  so there is no NOTICE content to reproduce. This record itself serves as
  the required attribution and statement of changes made (Apache License
  2.0 §4(b)/(c)).
- **Tests covering the port:** `tests/test_release.py::test_checklist_emits_needs_confirmation_for_config_change`,
  `test_checklist_no_findings_for_other_category`.

## 7. NeoLabHQ — context-engineering-kit

- **Repository:** https://github.com/NeoLabHQ/context-engineering-kit
- **License:** GPL-3.0 (confirmed via GitHub API)
- **Commit verified:** `8539779375f4e24b80f61476cfeaef330fa2d318` (`master`)
- **Reuse mode:** REFERENCE_ONLY / CLEAN_ROOM
- **NO SOURCE CODE OR SUBSTANTIAL TEXT COPIED.** No file from this
  repository was fetched or read. Only its license and existence were
  confirmed, specifically so it could be correctly excluded from any code
  reuse.
- **What ProjectKaizen target file(s) reference the same general subject:** `root_cause/five_whys.py`, `fishbone.py`, `a3.py`, `pdca.py`
- **Basis for the clean-room implementation:** Five Whys, Fishbone/Ishikawa,
  A3, and PDCA are generic, decades-old quality-management methodologies
  (Toyota Production System / Deming-cycle literature), not proprietary to
  this or any single repository. `root_cause/`'s dataclasses were designed
  directly from the build spec's own field-by-field description (spec
  section 11: "problem / why chain / evidence per step / confidence /
  termination reason" for Five Whys; "problem / current condition / target
  condition / root cause / countermeasure / verification / follow-up" for
  A3; "PLAN/DO/CHECK/ACT" for PDCA) — never from this repository's
  implementation, which was never read.
- **Tests covering this:** `tests/test_root_cause.py`.
