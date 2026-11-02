# v2.61 — Document publication and native Qt stage ownership

## Source of truth / release evidence

v2.60 on WolfCat-Studio: `qualification-20261030-222734-23219.tar.gz` contains `NATIVE_QT_SMOKE_PASS`, 704 passing headless cases and the Python-first gate. v2.61 is a new source candidate; native Qt has **not** been tested on that workstation. Versioned source archive is not a live Git HEAD.

## Decision A: source publication

The established `apply_proposal` writer checks an exact byte preimage, takes a private create-only backup, writes a same-directory temporary file, then atomically replaces the source. Between preimage verification and replacement, **two Studio processes could previously commit competing versions**. This is a source writer problem; adding a Qt mutex or duplicate document store cannot solve it.

Alternatives:

1. *Retry stale commits or auto-merge:* rejected. Changes program meaning and can erase edits.
2. *Lock the source inode while replacing it:* rejected. `os.replace` changes inode identity and could split writer coordination.
3. **Chosen:** a stable, private, persistent sidecar lock (`.filename.smi-lock`) per canonical path, held across preimage verification, backup creation and atomic publication using Linux `fcntl.flock`. The name and file persist deliberately; removing a lock while another process holds the old inode can create a second lock authority.

`SourceEditHistory.apply/undo/redo` and `SourceDocumentSession.commit` already funnel through `apply_proposal`; no alternate path was added. The writer refuses symlinked, public or non-owned lock files. Backup and exact-source checks still fail closed. Directory fsync is best effort for crash durability.

**Hard limitation:** `flock` is advisory. Non-cooperating editors and filesystem events may ignore it. Exact final byte checks reduce but cannot eliminate the narrow TOCTOU race against outsiders. This is not filesystem CAS, distributed locking, remote-filesystem coordination, or automatic merge. The user must resolve any detected external revision explicitly. Do not market this as universally race-proof.

## Decision B: native Qt qualification ownership

After a string of cross-stage failures, a separate window inside a single Qt process was insufficient isolation for all test cases. Each of three high-level smoke stages now gets a fresh Qt process:

- `recovery-subprocess` → `NATIVE_QT_RECOVERY_PASS` (25s stage deadline)
- `document-subprocess` → `NATIVE_QT_DOCUMENT_PASS` (35s)
- `integration-subprocess` → `NATIVE_QT_SMOKE_PASS` (75s)

The common launcher, production widget paths and existing GUI logic remain in use. A stage must exit zero **and** emit its exact final marker. Timeout, callback traceback or missing marker blocks release and retains `RUN-ALL` diagnostics. The overall default smoke deadline is now 150 seconds, covering the separate bounded processes.

We rejected (a) manually clearing private registries between stage tests, and (b) treating process exit status as sufficient evidence. The broader integration smoke remains stateful; splitting every remaining feature fixture is a later work item, not a completed claim.

## Acceptance and remaining work

Headless checks include two independent Studio writers racing on the same file (one commits, one stale-rejects), a child blocked behind a stable lock, refusal of unsafe locks, committed undo blocked after another process changes a file, and dirty source session preservation. Shell tests simulate recovery failure, document failure and missing PASS marker. Full existing headless regressions and Python-first gate must pass without relaxing older contracts.

Required user-host check: run installer, inspect `QT_STAGE` logs and see both recovery/document and main integration markers. No native PASS can be inferred from headless-only checks.

After qualification: close interleaved text/graph commit ordering and source alias characterization; then further split the stateful Qt test fixture and begin the smallest *graph-owned* Python-only ProgramGraph proof. Avoid inventing a second parser, source editor or language registry.
