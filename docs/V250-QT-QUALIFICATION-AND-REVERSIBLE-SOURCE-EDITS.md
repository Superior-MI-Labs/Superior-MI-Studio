# v2.50 | Qt hang correction and reversible source transactions

## Baseline

v2.49 did not finish native Qt qualification on the user's Linux Mint host: the installer remained at “Running native Qt offscreen smoke…” until interrupted. Headless 597 tests were previously green, but **do not qualify v2.49 native Qt**. This patch is based strictly on the supplied v2.49 ZIP; no live repository HEAD was established.

## Root cause

`qt_smoke.py` calls `_ask_stored_call()` (modal `QDialog.exec()`) and uses `QTimer.singleShot(110, accept_call_form)` to accept it. The timer callback evaluates `isinstance(widget, QDialog)` but `QDialog` was not imported at module scope. `NameError` inside the callback meant the dialog could remain open in its nested event loop forever. The smoke script never completed, and the installer only printed the broad native-Qt step banner.

**Corrections within existing owners:**

1. Import `QDialog` at module scope. The timer callback fails explicitly when its expected dialog/input does not exist rather than silently returning.
2. The existing Qt exception recorder now rejects the current modal dialog when a callback raises. The normal smoke test then fails qualification, rather than continuing to wait on a blocked `exec()`.
3. `RUN-ALL.sh` bounds the entire offscreen subprocess using GNU coreutils `timeout` with a TERM/KILL escalation; it prints the timeout diagnosis, retains `qt.log` with `QT_STAGE` breadcrumbs, emits the report tarball, and refuses install promotion. Default is 240 seconds; `SMI_QT_SMOKE_TIMEOUT` can override this for diagnostic testing. This is a last-resort safeguard, **not a substitute for fixing a hanging callback**.
4. A native smoke assertion now locates the View menu by identity, not its ordinal, because a real Edit menu changes menu positions.

## Next coherent slice: source-backed graph edit history

**Rejected:** mutable Qt graph undo stacks, untracked restoration from backup filenames, in-place rewrites bypassing `apply_proposal`, or undo that ignores changes made externally.

**Implemented:** a bounded `SourceEditHistory` in the existing `python_edit.py` transaction owner. Each approved graph proposal and saved valid text edit passes through `SourceEditHistory.apply()` into the original `apply_proposal()` atomic/backup path. Undo applies an inverse *EditProposal* requiring the exact previously committed candidate bytes; redo reapplies the original proposal. Both use existing preimage checks and create-only backups, and both rebuild the Python graph from saved source. A new edit clears redo. Stale external modifications cannot be overwritten. History is per file, in memory, limited to 16 transactions per file and 8 tracked files. It does not survive restart; on-disk backups do.

**Controls:** focused Python graph `Ctrl+Z` and `Ctrl+Shift+Z`; Edit menu `Ctrl+Alt+Z` and `Ctrl+Alt+Shift+Z` as explicit global shortcuts. Text-editor-focused `Ctrl+Z` remains Qt's native unsaved-text undo. There is no dishonest claim that arbitrary rendered wires are directly editable: only adapter-qualified source operations are committed.

## Verification and future work

- Local 606/606 headless tests PASS, including nine new regression tests for undo/redo, stale refusal, history bounds, shared saved-text history, import scope, and a genuine stalled shell subprocess ending with a preserved failure report. Python-first gate PASS. PyQt6 unavailable in patch-authoring container.
- Native smoke now exercises committed edit → undo → redo → undo using real Qt window actions; **this must pass on the user's Linux host** before v2.50 is host-qualified.
- Still open: general visual source-node deletion, safe disconnection, arbitrary control-flow rewiring, source editing with temporarily invalid syntax, and comprehensive user-experience review. Those must be designed from Python AST semantics, not a parallel graph state. No second language adapter.
