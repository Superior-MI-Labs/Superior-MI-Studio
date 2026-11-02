# v2.56 — Phase 1: draft history and external-disk conflict observability

## Evidence and baseline

The supplied `qualification-20261030-214445-6431.tar.gz` provides 654 headless passes and `NATIVE_QT_SMOKE_PASS` for the **v2.55** application on WolfCat-Studio. No app traceback appears in the native log. This qualifies the v2.55 resource-tab route repair, **not** the new v2.56 shortcuts.

## Architecture choices

1. **Draft history remains with `SourceDocumentSession`.** A bounded list of character deltas stores reversible unsaved text edits. `QPlainTextEdit` is a temporary view with Qt undo disabled, so switching two tabs that point at one file does not switch undo authorities. The same source document owns parsing, saved bytes, and draft history. Maximum: 128 edits and 8 million delta characters (subject to earlier truncation); no duplicate full-file snapshots per keystroke.
2. **Committed history stays in `SourceEditHistory`.** Its guarded disk transactions, preimage equality, backups and explicit Ctrl+Alt+Z commands do not become speculative graph-scene edits. Undoing an unsaved text draft does not modify disk; a save commits the active revision, and undoing after save produces a new unsaved revision.
3. **Disk conflicts are observed, never auto-merged.** A read-only `inspect_external()` marks a changed or unavailable path without mutating the live draft. It is checked on source-tab activation, explicit Check Python disk changes, and before committed publication. The guarded source writer still provides final preimage verification. Reload requires a deliberate user action for dirty documents and preserves shared session identity.
4. **Qt stays thin.** It invokes session.undo/redo, loads the resulting revision and reuses the same source projection. No second document manager, parser, source writer or language adapter.

## Deliberate limitations

- Qt native interaction qualification is pending the actual Linux host report. Headless AST inspection is not a substitute.
- No automatic disk-file watcher or background merge. Explicit check, tab activation, and guarded publication are the supported gates.
- Text-draft and committed-source histories are distinct; full interleaved semantic undo for source and graph is not yet qualified.
- Unsaved crash recovery has not been implemented. It requires a considered persistence/recovery policy and consent, not silent temporary files.
- Native graph-owned `ProgramGraph` and other language adapters remain deferred until source-document lifecycle gates are qualified.

## Qualification

Run `RUN-ALL.sh` on WolfCat-Studio and upload the resulting report. The new `QT_STAGE document-draft-history-and-external-changes` must pass, with no callbacks or timeouts. Reconfirm the existing resource/navigation and function-authoring native assertions. Any failure blocks release promotion and preserves the last qualified installation.
