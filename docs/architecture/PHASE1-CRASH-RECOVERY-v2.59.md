# v2.59: Crash recovery for source-owned Python documents

**Implementation checkpoint:** source-owned recovery candidate, native Linux Qt qualification **OPEN**. This is part of v3.1 Phase 1, not a graph compiler, a second source owner, or a claim of complete IDE readiness.

## Problem and alternatives

v2.58 holds unsaved edits only in an in-process `SourceDocumentSession`. A crash or loss of power drops that draft, even though the editor correctly preserves it through tab changes. `SourceEditHistory` protects committed edits, not unsaved text. This is an actual data-loss gap.

- A: Periodically write unsaved drafts to the original `.py` file. **Rejected**: turns incomplete edits into unexpected published source, violates guarded-source preimages, loses separation between Save and recovery.
- B: Store Qt widgets or full duplicated document sessions in a second serialized state store. **Rejected**: duplicates authority and risks restoring stale scene data as current semantics.
- C: Write a **non-authoritative crash receipt** containing path, exact saved-source digest, editor text, and revision. Offer explicit recovery back into the existing session, then parse normally. **Implemented.**

## Owners and data flow

`SourceDocumentSession` (`source_editor.py`) remains the sole live source owner. The new `draft_recovery.py` owns **only private crash receipts**. Qt starts a 950 ms debounce on text changes and draft undo/redo, flushing all open dirty sessions; it also flushes when switching workspace tabs. Recovery is offered by the existing source-open flow; no new editor, parser, graph registry, file writer, or cross-process auto-merge exists.

Source text update → revisioned session → bounded/private atomic receipt. After an abnormal exit, reopen `.py` → read receipt → verify path and saved-source SHA-256 against the newly opened file → **user explicitly chooses recovery** → live session receives text → existing Python parser/graph. A changed file blocks restoration and retains the receipt for manual handling. No recovery receipt is evaluated or published as Python automatically.

Source Save continues through the existing backup/preimage-guarded source writer. A successful Save or explicitly approved discard retires this session's receipt. An interrupted shutdown leaves receipts intact. Recovery files from other processes have independent random IDs; no timestamp-based winner can overwrite the source.

## Storage and security

`$SMI_RECOVERY_DIR` when set, otherwise `$XDG_STATE_HOME/superior-mi-studio/recovery`, falling back to `~/.local/state/superior-mi-studio/recovery`. Directory mode 0700, file mode 0600. Entries are bounded, versioned JSON; write goes to a same-directory temporary file, fsync, then atomic replacement, then a supported directory fsync. Path, base, and contents are checked before use. Symlinked entries and insecure recovery directory permissions are refused. Corrupted records remain for manual review rather than being deleted or shown as valid.

The 950 ms timer means the most recent keystrokes can be lost if a process crashes before the next snapshot; this does not guarantee zero-loss recovery. The receipts contain actual unsaved source code; users should protect their home directory and backups. There is no automatic age-based deletion or cross-process reconciliation yet. Ordinary source files are untouched until the user explicitly saves.

Native Qt smoke stages now include `crash-recovery-prompt-and-conflict` in an isolated window, and the smoke runner redirects recovery artifacts to a disposable test directory so test fixtures do not contaminate user recovery state.

## Verification and limitations

20 crash-recovery and 5 release/queue headless tests: clean/no-op, valid and invalid drafts, explicit restore/no auto-write, side-effect-free import, changed-base refusal, cross-file and dirty-document refusal, guarded commit, CRLF/Unicode, independent process tokens, private modes, symlink directory/record, corrupt/checksum/partial receipt, size/path bounds, environment and GUI routing. Existing 672-test v2.58 baseline remains in the suite. Native Qt interaction evidence is **not** available in the packaging environment.

Not implemented: multiple-process source-write CAS, session-wide persistent undo stack, graph-owned `ProgramGraph`, compilation, generation/publish, text/graph three-way reconciliation, arbitrary-graph editing, or language adapters. Keep those out of Phase 1 until the user qualifies this release on Linux.

## Host acceptance and rollback

Run `RUN-ALL.sh` using the supplied installer. Confirm the native `crash-recovery-prompt-and-conflict` stage (and the full existing smoke) completes with no traceback/timeout. After a manual edit, crash-recovery test with a disposable `.py`: type but don't Save, force-close Studio, reopen, approve recovery, confirm disk is unchanged until Save. Then edit the disk externally before recovery; verify Studio refuses to auto-merge and leaves the receipt intact. Install cleanup must not remove the previous qualified release until native PASS. Rollback is simply relaunching the previous version; the plain-text receipt is retained in the user state directory, not deleted by the installer.

**ADR:** ADR-026 remains PROVISIONAL pending host interaction and interrupted-process evidence. No other ADR changes.

**Release packaging consolidation:** `scripts/build_release.py` replaces the untracked external ZIP builder. It consumes the installer basename, scans release sources without symlinks/generated caches, generates the SHA-256 manifest, checks the ZIP with the existing installer validator, and hard-link publishes without overwriting an existing release. It is packaging tooling, not another application state authority.
