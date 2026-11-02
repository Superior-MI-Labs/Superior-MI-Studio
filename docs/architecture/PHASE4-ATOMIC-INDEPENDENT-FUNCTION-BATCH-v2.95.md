# v2.95 — Atomic independent multi-function reconciliation

## Problem / two approaches

Prior v2.94 independently authored source reconciliation was limited to one named function. Applying three separate imports creates three graph revisions, separate undo actions, and partial-application risk.

- **Rejected:** a separate whole-Python importer or a new persistent function-index/region owner. That duplicates compiler proofs and can silently claim ownership of unsupported source.
- **Adopted:** extend `_independent_function_plan` to a bounded, explicitly selected sequence of function names, while retaining the original one-function API as a thin adapter. Replace only those function AST nodes in the existing graph-generated candidate, feed the entire candidate through `_qualified_source_edit_plan`, and commit all proven changes using one existing graph transaction.

## Ownership / correctness

`SourceDocumentSession` retains all Python bytes, including unselected functions, comments, imports and syntax trivia. `ProgramGraph` retains graph revision and undo authority. The new `IndependentFunctionsReview` carries function names, source spans, revision/digest and proposed node operations as a **non-persistent receipt**; it is never a source owner, file writer or authorization by itself.

- Exactly 1–32 distinct valid identifier names explicitly selected; each must occur exactly once as a top-level synchronous function in both source and graph-generated baseline.
- Source function order need not match graph output order. Unsupported structures, changed signature, duplicate names, decorators and unqualified effects reject the entire candidate.
- All selected functions are proved together against complete graph re-lowering; all unselected generated functions retain their canonical AST. The compiler's existing 32-command cap still applies.
- The source session's current external-disk state, exact source revision/hash and graph revision are checked again immediately before commit. A successful import produces one atomic undo entry and never writes the source document.
- The existing Function menu offers **Review all graph functions in .py**, keeping selection explicit by the graph's authoritative function names; the earlier single-function command remains. Both use the same import action, which refuses stale review receipts.

## Qualification and limits

Headless regressions include two-function reorder, atomic undo, unselected code, no-op, duplicates, decorators, unsupported region, stale graph/source and external changes. Native smoke exercises the same user-facing review/import handlers. Native Qt must pass on Linux before promotion.

Not implemented: ambiguous mapping by source proximity, arbitrary Python-to-graph conversion, partial import after one failure, persistent mirrored source index, automatic source rewriting, or cross-file edit batches.

## Release-report isolation

The Linux qualification-and-launch script creates a run-specific timestamp marker before the installer runs, and only extracts an archive newer than that marker. A failure before report creation now does **not** present a previous build's archive as this build's results. The release contract test verifies the marker. This is a delivery correctness fix, not a second log collector or change to the installer's rollback and cleanup behavior.

## Faster qualification without new test infrastructure

The existing Actions workflow gains one isolated `native-qt` job (Ubuntu system PyQt6, offscreen Qt smoke, artifacts on failure). This catches actual signal/slot, widget lifecycle and route failures earlier than the user's installer, while keeping the required Mint host acceptance gate. No second Qt smoke implementation was added. `doctor.sh` now gets the printed version from the authoritative `install_linux.VERSION` rather than carrying a stale version banner.
