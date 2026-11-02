# v2.60 — Recovery acceptance and Qt qualification isolation

## Host evidence and failure boundary

v2.59 was rejected on WolfCat-Studio at `QT_STAGE crash-recovery-prompt-and-conflict`: after the test attempted to accept a recovery prompt, the active session was not proven to contain the draft. The prior assertion did not record the selected QMessageBox result or the intermediate session identity, so the exact reason cannot be proven from the submitted traceback alone. A green headless session round-trip does not prove a native UI choice was applied.

## Architecture decision

We compared three approaches:

1. Relax the assertion or retry opening the file. **Rejected.** Can hide discarded drafts or duplicate prompts.
2. Add another GUI recovery authority/controller. **Rejected.** The existing `SourceDocumentSession` and `DraftRecoveryStore` own source revisions and recovery receipts already.
3. **Implemented:** Make the smoke test click the actual `QMessageBox` buttons; require the selected draft to become the active session revision; isolate recovery interactions in a separate Qt process; use `activeModalWidget()` rather than choosing an arbitrary visible top-level widget. The production recovery method additionally checks approved recovered text and dirty state before returning the session.

The same source session and guarded disk writer are retained. No new document manager, parsing engine or compiler is introduced.

## Qualification and diagnostics

- `test-qt-offscreen.sh` runs the **recovery-only** Qt process first, then the wider smoke process. A recovery failure stops the entire qualification before integration runs.
- `QT_STAGE recovery-subprocess`, `QT_STAGE recovery-process-init` and `QT_STAGE crash-recovery-prompt-and-conflict` distinguish the stages. `NATIVE_QT_RECOVERY_PASS` must appear before `NATIVE_QT_SMOKE_PASS`.
- The existing test launcher isolates `SMI_RECOVERY_DIR` under `mktemp -d` and cleans it on exit, so fixture journals do not affect real user recovery data. No extra recovery store was introduced.
- A recovery selection must publish the exact draft to `SourceDocumentSession` **and** Qt must display that revision. An unaccepted prompt retains the recovery file and original source.
- Headless checks cover the subprocess order, rejection propagation, UI button-use source contract, and existing recovery safety invariants. Native PyQt behavior remains unqualified until tested on WolfCat-Studio.

## Next architecture work

After a clean native run, resume document-lifecycle closure and independent-process save conflict tests. Separate the remaining stateful Qt smoke areas behind independently created fixtures; preserve a smaller whole-IDE integration test. Next major product capability is a minimal Python-only `ProgramGraph` proof after document authority is qualified. Do not add a second language adapter or graph-only source writer.
