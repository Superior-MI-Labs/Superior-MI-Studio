# Studio Architecture v3.1 — Independent Design-Pass Review

**Date:** 2026-10-30. **Review scope:** internal architectural consistency, v2.50 code evidence, agent scope control, package cross-reference and executable test evidence. This is *not* proof the new architecture works; it is design validation before an implementation prototype.

## Design questions and dispositions

| Check | Question / adversarial scenario | Resolution / evidence | Disposition |
|---|---|---|---|
| DP-01 | Could graph-first and text-first both change one function without control? | No: one owned document/region, generated source branch has shared sync base and explicit 3-way reconcile | PASS DESIGN |
| DP-02 | Could saving an incomplete graph fail because a node lacks an operand? | Structural save independent of semantic generation, missing operand retained with diagnostic | PASS DESIGN |
| DP-03 | Could 'compile valid nodes only' drop a critical branch? | Publication at complete function/dependency-closure boundary; reachable invalid required control blocks | PASS DESIGN |
| DP-04 | Can arbitrary Python source be imported losslessly as editable graph? | Not guaranteed; preserve original text/source island, explicit unsupported mappings | PASS DESIGN with defined limitation |
| DP-05 | Can the renderer invent source logic from visual edge placement? | No; immutable descriptor and adapter qualification own semantics | PASS DESIGN |
| DP-06 | Are prototype sliders/audio rows accidentally executable operations? | No; legacy draft and ProgramGraph separate formats/authorities | PASS DESIGN |
| DP-07 | Can a node move/recolor change generated output? | No; program and presentation separated; semantic hash invariance test required | PASS DESIGN |
| DP-08 | What happens if graph is invalid while previous .py is valid? | Last-good output remains; generation records blocked status, no write | PASS DESIGN |
| DP-09 | Does a source graph show stale AST as current during invalid typing? | No; analysis revision stamped and stale label mandatory; no semantic edit on stale projection | PASS DESIGN |
| DP-10 | What happens if `.py` is externally edited after Generate but before Publish? | Conditional preimage check rejects, edits preserved; diff/merge/save-as offered | PASS DESIGN |
| DP-11 | Can a call with two result consumers execute twice? | Unknown/impure effects preserved, bound value materialized once or lowering blocked | PASS DESIGN, needs runnable proof |
| DP-12 | Can a program graph be translated to unrestricted Python control-flow? | No; structured subset first; arbitrary graph sketches allowed but unsupported lowering explicitly blocked | PASS DESIGN with defined limitation |
| DP-13 | Are file/tab/session IDs conflated? | No; document, URI, view, revision and hashes distinct | PASS DESIGN |
| DP-14 | Is file/graph undo implicitly the same thing? | Corrected v3.1: document edit history vs explicit published artifact rollback separated | PASS DESIGN after correction |
| DP-15 | Is any semantic capability duplicated in GUI? | Current implementation yes; RF-05/RF-06/RF-09 and E1/E5 remove duplicated qualification with parity tests | ACCEPTED MIGRATION DEBT |
| DP-16 | Is `gui.py` huge because of avoidable new subsystems? | Current 5,108 LOC; do not infer bug from size; extract only with ownership proof | PASS DESIGN |
| DP-17 | Could an untested new file writer destroy user data? | Keep guarded existing writer; new graph persistence requires temp/atomic/preimage/recovery tests | PASS DESIGN, implementation gate |
| DP-18 | Are original host Qt failures forgotten? | Baseline explicitly not host-qualified, watchdog and callback-traceback criteria retained | PASS DESIGN with BLOCKED HOST TEST |
| DP-19 | Is portability included? | Linux native first; Windows launch path and encodings/paths tested before declaring multi-OS shipping | PASS DESIGN with future release gate |
| DP-20 | Is security a later add-on? | No auto-execution on opening; trust checks for project tool launches, untrusted graph JSON size/depth | PASS DESIGN |
| DP-21 | Is a second language adapter prematurely needed? | Mock adapter to test neutral boundaries; actual second language after Python proof | PASS DESIGN |
| DP-22 | Are source identities stable when lines move? | Conservative match, ambiguous continuity dropped; preserving semantics preferred to inaccurate layout | PASS DESIGN with mapping experiment |
| DP-23 | Can an agent treat this blueprint as already implemented? | Status repeated throughout; acceptance rows separate baseline pass from PLANNED | PASS DESIGN |
| DP-24 | Are cleanups ordered to avoid rework? | Audit writers→live document→program graph→lowering→sync→interaction, with characterization before extraction | PASS DESIGN |
| DP-25 | Could restructuring explode into dozens of modules? | Candidate new modules have unique exclusive owners; no arbitrary file size splitting or framework construction | PASS DESIGN |

## Verified implementation facts

- 606/606 headless tests pass from supplied v2.50 archive (rerun; log included).
- Static AST inventory produced for all 30 `studio_native` Python modules; 70 `test_*.py` test files found.
- `source_editor.py` currently requires AST parsing/compilation for source text save proposal; new design deliberately separates ordinary Save Source from language validation.
- `model.py:write_state()` writes draft JSON with direct `Path.write_text`; native ProgramGraph persistence must use a guarded atomic write.
- `gui.py`, `python_graph.py` and `qt_smoke.py` contain large multi-responsibility methods; decomposition requires golden parity tests and not blind extraction.
- No native PyQt6 installed in review environment; actual host interaction remains unverified.

## Unproven, not to be misreported

1. Exact native ProgramGraph v1 grammar, JSON schema, version migration and rendering migration.
2. Sound graph-to-Python lowering for even a constrained subset until runnable semantics tests.
3. Source round-trip matching and synchronization of overlapping edits, beyond explicit conflict preservation.
4. Performance under large programs/recursive graphs in real target Qt environment.
5. Agent's actual repository version/HEAD and changes after the supplied v2.50 archive.

These are **open implementation proof obligations**, not reasons to abandon the architecture. Agents must report their experimental results before accepting provisional ADRs.

## Final design judgment

The chosen architecture is internally consistent and appropriately constrained. The biggest unavoidable cost—reversible graph↔source transformation—is explicitly acknowledged and isolated to language adapters. The near-term refactor plan is conservative about working source semantics and aggressive about removing duplicated authority. The correct next step is a verified ownership/refactor ticket, followed by live-buffer architecture, **not** a full speculative compiler rewrite.
