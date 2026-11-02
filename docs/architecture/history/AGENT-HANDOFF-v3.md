# SUPERIOR MI STUDIO — CODING-AGENT HANDOFF

**Authority:** Companion to `Superior_MI_Studio_Architecture_Blueprint_v3.md`. Read the master blueprint first; this shorter file is the execution contract.  
**Baseline:** Supplied v2.50 ZIP, not an assumed latest repository HEAD.  
**Status:** Architecture proposal; not implemented. Last independently run check: 606/606 headless unit tests PASS; native PyQt6/host smoke not run here.

## The architectural decision

Superior MI Studio will support both **source-owned** programming files and **graph-owned** programming files in the same IDE, with one authority for a given document/region and a revisioned source↔graph synchronization mechanism. The graph-owned document saves *all* well-formed draft content, including incomplete or disconnected nodes. A separate Python compiler/generator emits only semantically qualified complete program units. Invalid source text can also be saved in text-owned buffers. Never equate `Save Graph`, `Save Source`, `Generate`, `Publish`, `Validate`, and `Run`.

Do not add a second runtime, duplicate graph registry, second source writer, Python-specific code inside core Qt rendering, or an untested universal IR. Build Python-first and let a later language adapter own its own semantics.

## First actions before changing code

1. Inspect the actual repository HEAD, status and installed environment. Identify whether the supplied v2.50 ZIP differs. Use a dedicated worktree/branch; do not overwrite user projects.
2. Read the master blueprint and these project files: `README.md`, `docs/PYTHON-FIRST-READINESS-GATE.md`, `docs/V230-OPERATION-SCHEMA-AND-FUNCTION-BOUNDARIES.md`, `docs/V242-COMPOSABLE-PYTHON-DATAFLOW-AND-IDE-REVIEW.md`, `docs/V249-FUNCTION-AUTHORING-MILESTONE.md`, `docs/V250-QT-QUALIFICATION-AND-REVERSIBLE-SOURCE-EDITS.md`.
3. Locate current owners: `model.py`, `semantic_contract.py`, `python_graph.py`, `source_editor.py`, `python_edit.py`, `python_authoring.py`, `authoring_contract.py`, `source_connection.py`, `operation_catalog.py`, `authoring_actions.py`, `graph_routes.py`, `navigation.py`, `presentation_state.py`, `gui.py`, `qt_smoke.py`.
4. Run baseline tests; record exact results. Validate native Qt on user's Linux host and retain log/tarball. If host test cannot be run, state **not qualified**, never imply success.
5. Map all file writers, document dirty state holders, undo/redo implementations and graph registry creation points. There must be no unknown second path.

## Phase dependency order

| Phase | Required deliverable | Acceptance |
|---|---|---|
| 0 | Reproducible baseline, ownership/dependency map, host Qt evidence | No unknown writers; regressions recorded |
| 1 | One revisioned in-memory source buffer, valid unsaved re-projection, invalid text persistence | Two tabs share buffer; invalid text can save; graph stale status honest |
| 2 | Native versioned executable ProgramGraph, separate from prototype format | Arbitrary incomplete nodes and annotations save/reopen with stable IDs and undo |
| 3 | Graph-owned Python lowering for bounded functions/calls/results | Build two functions visually; generated program passes compile and behavior tests; last good `.py` retained on block |
| 4 | Function-scoped provenance/mapping and supported source→graph import | Add→Multiply text edit imported; unsupported text preserved; concurrent change conflict detected |
| 5 | Blueprint-quality interactions through shared commands | Create, connect, disconnect, reconnect, delete, undo in native Qt without duplicate semantics |
| 6 | Expanded Python control-flow coverage | Each construct qualified separately with effects/return tests |
| 7 | Conventional IDE workbench integrations | LSP, tools, project services follow document/revision contract |
| 8 | Neutral adapter/second language readiness | Non-Python adapter requires no Python-specific Qt branching |

**First implementation ticket:** Phase 0 then Phase 1, not an all-at-once graph compiler rewrite. A graph compiler is a Phase 3 bounded spike after ProgramGraph schema is proven.

## Important mandatory rules

- A structurally valid native graph remains savable when semantically invalid. Unknown/missing required inputs are diagnostics, not reasons to delete author work.
- No required bad branch, effectful call or dependency may be silently dropped from a published runnable function. Initial generation unit is a **complete function**, with validated module-level dependencies.
- Graph layout, panning, node color, reroute and collapse never affect program semantics.
- The existing `GraphDescriptor` is an immutable *view projection*, not editable graph authority. Its present `origin` discriminator contains source/draft/resource; add a formally versioned `program` origin for executable graph projections, not an ad hoc misuse of `draft`.
- Python `ast` and symbol-table analysis remain source projection authorities; code emission from graph uses a separate Python-language-owned structured lowering path. Compiler analysis does not belong in Qt.
- Unknown effectfulness stays unknown; don't double-invoke `f()` because two result pins consume the value.
- Exact Python source is preserved on view/import; don't normalize formatting/comments or use `ast.unparse` as a lossless formatter.
- Qt source and graph editors must share document revisions; stale results are dropped, external file changes rejected or reconciled, and unresolved graph/text edits are preserved.
- No second real language until the Python-first gate, native Qt gate and the staged graph/source authority gates pass.
- Proposals must include base identity/hash, diagnostics and source diffs before publication; all source writes use the protected persistence path.

## Required implementation methodology

For every ticket: **inspect → compare two approaches → establish owner/contract → implement smallest vertical slice → adversarial tests → baseline tests → native UI qualification → evidence report**. Favor modifying correct existing owners over creating new files. New modules need a named exclusive responsibility and a proven acceptance test. Stop for architecture review if a second source of truth appears.

### Agent completion report template

```markdown
Baseline commit/archive and environment:
Phase and ticket ID:
Existing modules reviewed:
Architectural problem and root cause:
Approach 1 / approach 2 / decision:
Data authority and transaction impact:
Files and contracts changed:
Semantics supported and explicitly unsupported:
Exact headless test command, count and result:
Native Qt test command and report (or BLOCKED):
New regression tests and expected failures:
Source preservation / draft preservation proof:
Effects/order/provenance proof:
Install/recovery/rollback proof:
Debt removed vs added:
Decision: PASS / FAIL / NEEDS ARCHITECTURE REVIEW:
Next minimal task:
```

## Stop conditions / rejection criteria

Reject or halt when a change: (1) makes Qt own Python semantics; (2) creates a second writable node registry or file writer; (3) silently rewrites existing `.py`; (4) converts failed graph compilation into hidden `pass`, `None` or missing guard; (5) loses invalid source or graph drafts; (6) drops external-change detection; (7) claims runtime purity from absence of white exec pin; (8) packages a build without native host qualification evidence; (9) expands language support to conceal unfinished Python architecture; or (10) requires broad rewrite without first proving the bounded behavior.

## Required evidence files for each delivered patch

- `ARCHITECTURE-DECISION.md` for any new module/contract; include alternatives and boundary map.
- `QUALIFICATION.md` with exact commands, counts, host-specific Qt status, screenshots/log paths, limitations.
- Updated `Studio_Architecture_Acceptance_Matrix.csv`: mark a case PASS **only** if executed; otherwise `NOT_RUN`/`BLOCKED`.
- A source patch and/or tested ZIP with safe installer instructions and rollback; do not replace a known-good installation on failed qualification.

**Definition of done:** The user can build Python visually, preserve incomplete experiments, generate correct code, edit supported source constructs, recover unsupported changes without loss, and continue in normal IDE tools. Every intermediate phase must move toward that behavior without introducing contradictory ownership.
