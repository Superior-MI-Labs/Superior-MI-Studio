# Phase 1 — v2.52 baseline, document ownership and in-memory Python analysis

**Status: implementation foundation only, not a finished live-editing GUI.**
Baseline is the *user-supplied* `Superior_MI_Studio_v2.52_Codex_Ready.zip` (SHA-256 `520f91ac0761b334155e507cc43fc1afb87204b5f6dc78a3c6c104c5cb008d01`). The underlying application v2.52 ZIP has SHA-256 `b3f33f08839ee19919d07c00d90c59c4e9d33ce94a851c82ab6253bb8c8906ea`. No live Git HEAD or dirty state was available. This patch was developed against an isolated extraction of the Codex-ready archive, not an asserted live working tree. **The latest v2.52 Linux Qt host qualification was not supplied; native Qt remains unverified.**

## T00: factual ownership inventory

| Owner | State/mutations observed | Next boundary |
|---|---|---|
| `studio_native/python_graph.py::PythonDocument` | Reads `.py` bytes, owns AST/symbols, source snapshot and graph projection; previously disk-only | Now supports identical parsing of explicitly supplied bytes; no writer or mutable buffer added |
| `studio_native/source_editor.py` | UTF-16 spans and Qt-text-to-source proposal conversion; strict valid-Python gate | The same newline/encoding conversion can produce a read-only preview; text save remains strict until document-session migration |
| `studio_native/python_edit.py::apply_proposal` and `SourceEditHistory` | Sole observed Python file writer and committed-source undo/redo; SHA/preimage guarded and backup-producing | Reuse when explicit disk publish is introduced; never write a temporary file merely to parse a live revision |
| `studio_native/gui.py::_source_editor_changed`, `_load_source_editor`, `save_python_editor` | Qt text widget and `_source_editor_dirty` currently own unsaved text, while `python_doc` represents saved source | Not yet migrated; two-tab switching and invalid-source saving remain limitations |
| `studio_native/gui.py::_resync_other_source_tabs`, `reload_python_source` | Pushes reloaded disk parser snapshots to existing source tabs | Future revisioned session should publish *one* parsed revision to all views; no second tab parser store |
| `studio_native/graph_routes.py::resolve_graph` | Already accepts a supplied parsed `PythonDocument`; validates exact path and projects through one descriptor engine | No change necessary; new in-memory snapshot uses existing route/descriptor contract |
| `studio_native/semantic_contract.py` | Read-only validated `GraphDescriptor`, not mutable code | Unchanged; native executable ProgramGraph remains experimental |
| `studio_native/authoring_actions.py`, `python_authoring.py`, `source_connection.py` | Python semantic action discovery, creation and guarded graph edit proposals | Unchanged; no second operation catalog/validator |
| `studio_native/model.py`, `resource_graph.py` | Legacy presentation prototypes and filesystem/resource graph, respectively | Unchanged; neither is an executable Python program graph |
| `RUN-ALL.sh`, `doctor.sh`, `qt_smoke.py` | Release headless+host Qt qualification and artifacts | No changes; PyQt6 not installed in this environment |

## T01: characterized behavior

- Saved `.py` and an identical in-memory source snapshot produce equal descriptors in whole-file and focused function modes.
- A valid unsaved revision can be analyzed through the same provider **without** writing to disk; two distinct view routes can reference the *same* parsed revision object.
- Invalid text raises a precise analysis error and leaves prior snapshots and disk unchanged. **The current Qt editor still does not save invalid Python**: that acceptance criterion is deliberately open, not falsely marked complete.
- UTF-8 BOM, non-BMP Unicode, PEP-263 encodings and CRLF are characterized. Mixed line endings remain a fail-closed unsupported edit in the current text adapter.
- External disk changes still defeat a stale EditProposal; merely projecting an in-memory draft never writes. Parsing never imports or executes source code.
- A whole-file function node is an interface summary and may not change when body expressions change. Semantic-body diff tests must compare the focused function graph.

## T02: design comparison and decision

**Option A — continue using a disk parse as the only graph input.** Least code, but cannot represent an unsaved revision without a filesystem mutation. Temporary-file parsing also breaks exact identity/provenance and creates unintended write paths. Rejected for the live-editor architecture.

**Option B — make the existing Python parser accept exact source bytes, and keep existing route/descriptor ownership.** Selected. `PythonDocument.from_bytes()` shares the same private parsing/AST/symbol indexing as `PythonDocument(path)` and uses exact file identity. `preview_source_change()` converts Qt-normalized text using the same candidate-byte helper as the existing guarded editor proposal. No new parser, persistent buffer, registry, writer, or graph authority is introduced.

**Session-owner decision for the next implementation gate:** evolve `source_editor.py` and the existing GUI source-tab/session path to a single revisioned document session, then remove `_source_editor_dirty` as an independent ownership flag once native parity is proven. Qt becomes a view of the canonical buffer. The session must retain invalid text and diagnostics, saved-disk preimage, revision number, and at most one parsed snapshot per revision; graph projections use that snapshot only. Committed-source undo belongs to the existing guarded writer, and any buffer history must be reconciled into one document history rather than layered as a second undo stack.

Do not implement this by adding a permanent detached `SourceSession` that duplicates the Qt buffer while the old path remains active. Do not silently reparse invalid text as its last-good snapshot without a stale marker. Do not save an invalid source candidate through an unguarded writer.

## T03 boundary and stop condition

**Implemented:** read-only in-memory analysis seam; disk parser behavior unchanged, no GUI wiring. **Not implemented:** live Qt draft ownership, unsaved graph auto-refresh, invalid-source save, multi-view synchronization, source revision undo/recovery or any graph-owned `ProgramGraph`. These require migration and real native Qt evidence.

Next coherent change: add characterization of actual Qt text/tab lifecycle; implement one revisioned buffer owner with explicit source identity, saved preimage, and invalid-source diagnostics; adopt it in *one* source view, remove replaced alias logic, and run native multi-tab, invalid-edit and external-change scenarios. Do **not** start Python graph compilation or a second adapter before that gate.

## Verification and rollback

`bash scripts/agent-verify.sh --headless` and the 14 new `tests/test_v253_live_source_projection.py` scenarios are the required local gate. On a PyQt6 Linux host additionally run `bash scripts/agent-verify.sh --native` before promotion. Rollback: restore v2.52 archive; the added parser entrypoint changes no on-disk schema, installer behavior, user preferences, or Python edit format.

ADR change: **none**. Implements a foundation for ADR-001, ADR-004, ADR-005, ADR-008, ADR-010 and ADR-016 without claiming those larger acceptance gates pass.
