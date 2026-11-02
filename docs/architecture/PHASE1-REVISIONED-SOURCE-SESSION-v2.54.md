# v2.54 — Revisioned Python source document and live GUI projection

**Scope:** Phase 1 document lifecycle only. Source-owned Python remains authoritative; no graph-owned executable program or new compiler. This is a source archive candidate awaiting native Qt qualification on Linux Mint/WolfCat-Studio.

## Architectural comparison

- A: keep Qt's text widget as the only buffer and reparse on disk save. This preserves fragmented tab state, forbids invalid-source persistence and prevents truthful unsaved graphs. Rejected.
- B: add an independent mutable graph and synchronize it bidirectionally with the Qt text buffer. This introduces two programming authorities before conflict resolution exists. Rejected.
- **C (implemented):** extend the existing `source_editor.py` boundary with one `SourceDocumentSession` per file. Qt is a view, and `PythonDocument.from_bytes()` remains the sole parser. Only the existing `SourceEditHistory`/`apply_proposal` path can publish file bytes. `GraphViewSessions` remains the presentation/navigation owner.

## Invariants and data flow

`QPlainTextEdit` → `SourceDocumentSession.update` (monotonic revision) → debounced `qualify()` → `PythonDocument.from_bytes()` → `resolve_graph` → all source tab projections. If parsing or graph resolution fails, the graph becomes unavailable for that revision; the source text and diagnostics are retained. The original source file is untouched until Save.

- **One per-file text authority.** The session retains text, exact saved raw preimage, encoding, monotonically increasing revision, one optional qualified AST snapshot and a diagnostic. The Qt editor's `dirty` variable is a compatibility readout of the session, not another stored document. Source views retain routes/cameras only.
- **No silent invalid-code execution or stale presentation.** Syntax-invalid files can be opened, edited, and saved as text, but they have no graph and cannot authorize visual edits. A graph appears again after the currently active revision parses. No source is imported or executed during these operations.
- **Safe persistence.** The session makes an `EditProposal(saved_raw, candidate)` and delegates to the existing guarded, backup-producing `SourceEditHistory`. Failure preserves the draft. Encoding, mixed line endings, size and symlink restrictions fail closed. Saving incomplete Python does not mean the program is executable.
- **Tabs.** Source views of one path share the same session and parser object after qualification; routes/cameras remain independent. A tab switch does not discard text. A bounded 32-document session cache is explicit; all dirty documents are considered at application exit.
- **Undo.** Committed-source undo/redo continues through `SourceEditHistory`; Qt's unsaved text undo remains a widget operation. This is not yet a unified all-revision undo architecture. The integration gate remains open.

## Evidence

- v2.53 baseline: 635 headless tests; v2.54: **649 headless tests passed**, including 14 source-session behavior tests. Python-first gate, doctor, and project setup checks passed in the isolated sandbox.
- Native Qt: **not available in sandbox**; `qt_smoke.py` has a new revisioned-source stage exercising invalid draft, invalid guarded save, valid repair and graph rebuild, but only a real Linux host report qualifies it. Do not mark complete from headless evidence.
- Still open: actual native Qt multi-tab view switching across dirty/incomplete files; merged/conflict handling after external changes; file watcher policy; cross-session undo, crash recovery; stale visual edit rejection during rapid editor mutations; performance profiling with large files. These must be addressed before graph-owned ProgramGraph or another language adapter.

## Next acceptance gate

Run the versioned `RUN-ALL.sh` on Linux Mint. Demand a clean `QT_STAGE revisioned-source-session`, no callback traceback and no timeout, then manually verify two source tabs from one file, unsaved edits flowing into both, invalid source save/reopen, external disk edit refusal, and switching among files while each has unsaved text. Preserve the report and back out to v2.53 on failure. Only then consolidate the remaining tab transition, external-change, and undo invariants.
