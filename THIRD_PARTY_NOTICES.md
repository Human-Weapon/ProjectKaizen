# Third-Party Notices

ProjectKaizen is MIT-licensed (see [LICENSE](LICENSE)) and has zero
third-party runtime dependencies — nothing in this file describes a
dependency shipped with the package.

This file records external sources that were **reviewed** during
development because they informed the design of specific ProjectKaizen
modules. Full detail — exact commit SHAs, files read, what was reused vs.
independently built, and the tests covering each — lives in
[docs/oss-reuse-manifest.md](docs/oss-reuse-manifest.md). No line of code
or substantial text from any source below was copied into this
repository; nothing here required binding attribution to ship, and this
file is provided as an additional, voluntary record.

| Source | License | Reuse mode | Detail |
|---|---|---|---|
| [addyosmani/agent-skills](https://github.com/addyosmani/agent-skills) | MIT | REFERENCE_ONLY | manifest §1 |
| [mattpocock/skills](https://github.com/mattpocock/skills) | MIT | REFERENCE_ONLY | manifest §2 |
| [obra/superpowers](https://github.com/obra/superpowers) | MIT | REFERENCE_ONLY | manifest §3 |
| [massimodeluisa/recursive-decomposition-skill](https://github.com/massimodeluisa/recursive-decomposition-skill) | MIT | REFERENCE_ONLY | manifest §4 |
| [openai/openai-agents-python](https://github.com/openai/openai-agents-python) | MIT | ADAPTED (tag resolution) + REFERENCE_ONLY (checklist) | manifest §5 |
| [chaunsin/agent-skills](https://github.com/chaunsin/agent-skills) | Apache-2.0 | ADAPTED (category taxonomy only) | manifest §6 |
| [NeoLabHQ/context-engineering-kit](https://github.com/NeoLabHQ/context-engineering-kit) | GPL-3.0 | REFERENCE_ONLY / CLEAN_ROOM — **no source read, no code copied** | manifest §7 |

## Apache-2.0 note (chaunsin/agent-skills)

The reused material is a category taxonomy (naming conventions for
grouping release risks), not code or substantial text — see manifest §6
for the exact scope. The source repository carries no separate `NOTICE`
file to reproduce (verified against its root directory listing). This
table row, together with manifest §6, constitutes ProjectKaizen's
statement of the Apache License 2.0 §4(b) changes made and §4(c)
attribution.

## GPL-3.0 note (NeoLabHQ/context-engineering-kit)

**No code or text from this repository appears anywhere in ProjectKaizen.**
Its license was confirmed only so it could be correctly excluded from
reuse. The general continuous-improvement methodologies it also documents
(Five Whys, Fishbone, A3, PDCA) are public, decades-old techniques, not
this repository's original work, and were implemented independently — see
manifest §7.
