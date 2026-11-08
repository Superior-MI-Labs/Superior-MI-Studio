# Phase 4: Linked-source precommit snapshot integrity (v2.127)

## Observed problem

`LinkedPythonSource.review_edits()` checked the link's disk/graph receipt before compiler proof and returned an advisory result without a final source-owner check. `LinkedPythonSource.import_edits()` called `import_generated_source_edit()`, which performs the compiler proof **and graph mutation** before returning to the link owner. A reentrant `SourceDocumentSession` edit, disk save or external write during proof could therefore commit a valid edit against an already stale source receipt. Invalid UTF-8 drafts could also escape as `UnicodeEncodeError` rather than an ordinary compiler refusal.

## Alternatives considered

- **A: Add a new transaction/snapshot manager or file lock across the two owners.** Rejected: creates a new owner, adds lifecycle work, and still cannot make arbitrary external filesystem writers participate in an atomic transaction.
- **B: Keep the existing compiler planner as the single authority, capture the source session revision/text/saved preimage locally, and move the linked graph commit after final conflict checks.** Selected. The link keeps only its existing accepted-source receipt; no new persistent state or mapping is introduced.

## Correct boundary

1. `_qualify_receipt()` still verifies original graph fingerprint, source revision, saved-source preimage, and disk status. The link captures `revision`, `text`, and `saved_raw` from that source owner once.
2. Review calls the existing generated-source compiler using captured text. On success or refusal, `_assert_current_source()` checks for revision, text, saved bytes, disk and graph conflict before returning any advisory review. Graph identity can advance through a proven undo/redo cycle as before.
3. Import calls the existing **non-mutating** `_qualified_source_edit_plan()` on the captured text, then validates the captured source and link receipts immediately before `ProgramGraph.edit_many()`. A failed proof never authorizes a partial graph edit. The no-op import branch also revalidates before refreshing link metadata.
4. After a successful graph transaction, only the accepted snapshot values advance the link receipt. Source text is not written, parsed at runtime, silently replaced or flattened into another owner.
5. Unencodable edited Python is rejected with `ProgramGraphError` at the existing compiler input boundary. No additional grammar is admitted.

The source/disk checks are optimistic: without cross-process file locking, another program can still change a file after the final check. The source publisher remains independently guarded; **this patch does not claim cross-process atomicity**.

## Evidence and limits

`tests/test_v2127_linked_source_snapshot.py` has ten new tests for unchanged success, review-vs-disk/dirty revisions, import-vs-disk/dirty revisions, failed-proof conflict priority, invalid encoding, linked graph changes, source save during qualification, and the no-op receipt. The v2.78/v2.79/v2.93 linked-source regression suites and full headless suite remain gates. Native Qt is unchanged and must be independently qualified through the established pipeline.

**Next:** Audit remaining root/secondary navigation branches against the existing view sessions and native parity tests. Do not remove the protected original root anchors or introduce a new route authority. The canonical current queue remains `docs/agents/NEXT-TASKS.md`.
