# HERMES OSS external feedback — remediation round 1

Anonymous external use of the five independent tools informed this evidence
record. It records only supplied observations and the disposition reached in
this round; it does not identify the tester or imply a shared runtime.

| ID | Observation | Classification | Disposition |
|---|---|---|---|
| EXT-PG-001 | Persistent decisions helped, but game-project traceability was used too sparsely. | DOCUMENTATION_GAP + CONFIRMED_CORE_BUG (P3) | FIXED: the traceability guide shows the memory graph, records, paths, relations, and bounded retrieval; context packs now retain relevant verification-evidence records. |
| EXT-AG-001 | Execution plans felt generic despite the possibility of rich caller knowledge. | UX_DEFECT (P3) | FIXED: AgentGear preserves caller-supplied actionable context and marks absent details unknown instead of inventing them. |
| EXT-SG-001 | Binary assets made static-analysis completeness ambiguous. | UX_DEFECT (P3) | FIXED: SkillGuard now distinguishes supported static analysis, unsupported/non-source assets, errors, and limit skips. |
| EXT-AB-001 | A real Windows encoding defect in the tested project was detected; 12/12 executions passed after that project was repaired. | PROJECT_SPECIFIC_REQUEST | NO_CORE_CHANGE: focused review found AgentBench's bounded subprocess capture, UTF-8 replacement decoding, console-safe output, and persisted result path intact. |
| EXT-PK-001 | A static web game with Python-only benchmark tooling received Python-packaging advice. | CONFIRMED_CORE_BUG (P3) | FIXED: packaging advice now requires Python product-code evidence, not an incidental tooling script. |

The tools remain conditional: use a tool when it contributes a real decision,
not as a ceremonial five-stage pipeline. Each repository's existing HERMES
documentation already states that integrations are optional and that no central
runner is provided.
