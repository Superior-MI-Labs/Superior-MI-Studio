# v2.140 — An independent compiler receipt cannot inherit a later graph revision

## Observed gap

Independent source proof can call into the bounded trial compiler and source
evidence locator. An adversarial/reentrant callback can mutate the original
`ProgramGraph` between the validated initial revision and the final review.
Before v2.140 the returned receipt used `graph.revision` at the **end**
of the proof, rather than the original requested revision. It could thus
mislabel commands that had been proven against an older graph. On a failed
proof, source-region attribution could mask a concurrent graph change.

## Alternatives

- **A: lock all graph editing during review.** Rejected: would introduce
  a new stateful synchronization owner and complicate Qt event handling.
- **B: use the existing ProgramGraph revision contract at proof and import
  boundaries.** Selected: check `graph.revision` against
  `expected_graph_revision` on failed proof, before source provenance
  mapping, and again after all provenance callbacks. The receipt records
  the *expected* proof revision, never a newer one observed late. Reject
  graph mutation during failed per-function diagnostics as a conflict too.
  The import path's v2.139 last graph-revision check remains authoritative,
  including empty/no-op batches.

## Tests and behavior

`tests/test_v2140_independent_graph_revision.py` contains six tests:
normal review/import; graph edit after successful proof; graph edit during
failed proof; graph edit during source evidence mapping; graph edit after
the plan but before import; and graph edit before a no-op import return.
The edits use the legitimate `ProgramGraph.edit('move_node')` API, not
unprotected private-state modifications. A layout edit still advances
the graph owner revision even when generated Python is unchanged, so the
receipt cannot silently reuse its old proof.

No other owner, editor, second compiler, graph state store, worker,
lock, AST adapter, or release pipeline is introduced. A v2.140 CI
PASS is not Linux Mint host qualification. Roll back to v2.139 on
spurious conflict refusals with stable revisions.

## Generated-source entry points share the same revision boundary

Public review_generated_source_edit and import_generated_source_edit also
use the existing _qualified_source_edit_plan, but formerly could return
an advisory receipt, a no-op or a stale failure after a reentrant graph
edit. Both now check the original ProgramGraph revision after successful
compiler proof and after a compiler refusal, before returning or committing.

tests/test_v2140_generated_source_revision.py adds seven regression tests:
ordinary review/import, stable no-op, mutated graph after successful review,
real import, no-op import, and both kinds of failed-proof diagnostic.
These checks use official ProgramGraph graph edits and no new compiler,
writer, lock, registry, document or graph store.
