# v2.93 — Qt Inspector lifecycle + linked Python reconciliation preflight

Status: implemented; native Linux verification pending. Date: 2026-11-02.

## Evidence and actual failure

The v2.92 host report `qualification-20261102-024544-43211.tar.gz` failed at `qt_smoke.py`'s `len(matches)==1` during an Inspector search update. The test queried all QObject descendants, while replaced result buttons were removed from layouts by `deleteLater()` only. Qt may keep them parented until the enclosing event loop dispatches deferred deletes. A count of all window descendants is not the count of currently presented results. Prior related failures involved graph revision aliasing; this one is a distinct widget-lifecycle problem.

## Options considered

- **A: allow stale buttons and loosen the assertion.** Rejected: stale buttons remain accessible and may retain captured edge IDs; masking the test creates ambiguity.
- **B: synchronously hide and unparent obsolete widgets, then schedule their destruction; scope callbacks and tests to the current results panel and render revision.** Selected: repairs ownership, does not change search engine or document semantics.

## Source reconciliation choice

- **A: independent Python differ/reverse compiler** would create a second semantic authority and potentially approve a patch the real lowering engine rejects. Rejected.
- **B: expose immutable read-only review from the exact existing generated-source lowering proof and share one linked revision/conflict gate with commit.** Selected. Each approved candidate is tied to graph's stable node/function identities. Full candidate still must re-lower and match complete Python AST (or exact bytes for generated edit dialog); unsupported code is refused and retained in its source owner. No general arbitrary-Python import is claimed.

## Contracts and tests

- `NativeLab._detach_inspector_widgets` removes visible widget ownership synchronously; all result callbacks check active Inspector panel, selected canvas and immutable graph identity. `qt_smoke` checks that the old result loses its QObject parent immediately and only current panel results count.
- `SourceEditReview` / `SourceEditChange` are immutable reports, not retained edit permissions. `review_generated_source_edit` calls `_qualified_source_edit_plan`, as does `import_generated_source_edit`; import revalidates the existing `ProgramGraph.revision` and source session before `edit_many`. `LinkedPythonSource._qualify_receipt` performs disk/source/graph conflict checks for both review and import.
- Negative tests: unsupported AST statements, invalid Python, stale preview after graph movement, source changes after review, external disk edits, source-trivia-only noop, undo/redo state restoration and multi-operation atomic edits.
- Required host stages: `QT_STAGE program-linked-source-review-preflight` and `QT_STAGE resource-revisioned-relationship-explorer`. No native QT qualification available in this container; do not promote until WolfCat-Studio reports all stages PASS.

## Rollback and migration

The schema, file formats, ownership and undo history are unchanged. Failed native qualification must preserve the previous versions and logs, and must not launch the candidate. No migration required.
