# v2.57 — Qt source draft keyboard dispatch and source-session integrity

## Host evidence

- Exact archive: `qualification-20261030-215120-6682.tar.gz`, for v2.56, Linux host WolfCat-Studio.
- `QT_STAGE document-draft-history-and-external-changes` failed when a Ctrl+Z key event left the Qt text view inconsistent with the expected previous saved draft. The report does not independently prove whether Qt's shortcut override swallowed the key or which object processed it.
- Existing `QPlainTextEdit` owns built-in Undo/Redo shortcut handling. v2.56 disabled its text undo stack but attached separate QShortcut handlers to the same keys, introducing conflicting dispatch routes. The explicit menu route and headless `SourceDocumentSession` history behaved correctly in previous tests. Remedy the event-routing boundary, not the text-model algorithms.

## Alternatives and decision

1. **Keep QShortcut and change focus/context/priority:** rejected. Qt's editor may still claim the standard undo shortcut, and priority/order is a fragile assumption. It leaves two dispatch paths for a single document command.
2. **Restore QTextDocument widget undo and synchronize it after tab switches:** rejected. Widget history becomes a second mutable source-history authority and is recreated when views reload.
3. **Use a thin specialized source text widget to intercept Ctrl+Z/Ctrl+Shift+Z and delegate to SourceDocumentSession:** implemented. It claims `QEvent.ShortcutOverride`, dispatches a single `KeyPress`, and preserves all other standard editing and menu paths. No new document data owner is added.

## Integrated changes

- `PythonSourceTextEdit` subclasses existing Qt source editor, accepts the relevant shortcut override, and calls `NativeLab.undo_source_draft` or `redo_source_draft` directly on key press. Auto-repeat does not create multiple history transactions. Older QShortcut connections are removed.
- Existing `SourceDocumentSession` delta history, revision/dirty state, parsing and disk preimage guards are untouched. The screen is rehydrated from the same session object after an accepted transaction.
- Qt cursor restore now bounds against `QTextDocument.characterCount() - 1`, since raw Python `len` does not represent Qt UTF-16 cursor units for non-BMP text.
- Native test verifies the editor subclass, the active session's changed revision, and the Ctrl+Z/Ctrl+Shift+Z visible result. Headless tests exercise the real subclass code under stubs to prove routing without installed PyQt6, but do **not** substitute for native Qt.

## Acceptance / boundaries

Required on WolfCat-Studio: `RUN-ALL.sh` must show a clean `QT_STAGE document-draft-history-and-external-changes`, complete all later Qt stages, print `NATIVE_QT_SMOKE_PASS`, and exit zero without Python callback tracebacks. An assertion failure or hang blocks release promotion.

This milestone is part of Phase 1 live document lifecycle, not the start of a graph-owned compiler. Still open: crash recovery policy, full interleaved text/committed source transaction history, independent-process concurrent save safety, and native graph program documents. No other language support is authorized.
