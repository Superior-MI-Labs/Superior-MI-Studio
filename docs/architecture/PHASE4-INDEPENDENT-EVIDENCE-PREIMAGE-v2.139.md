# v2.139 — Independent-source evidence remains inside the receipt proof boundary

## Identified failure

The independent-source compiler planned and proved graph changes against one
`SourceDocumentSession` snapshot and one ProgramGraph revision, then verified
the source/disk. It subsequently constructed advisory `change_lines` and
`change_spans` from the saved AST, **without a final owner recheck**.
A reentrant editor or external disk change during evidence building could
therefore return a stale review receipt. Worse, the receipt took
`graph.revision` *after* evidence building, potentially labeling a proof of
one graph revision with a newer one. The importer ordinarily requalifies,
but a review receipt must not misstate its evidence.

## Alternatives

- Rebuild the independent-source pipeline or persist another source snapshot:
  rejected (duplicates source and compiler authority).
- Add exception wrappers and undo stale receipts afterward: rejected
  (compensating recovery and misleading diagnostics).
- Consolidate the existing source/disk/graph preimage check into a private
  lexical guard inside `_independent_functions_plan`; call it after
  full-compiler proof, before final error attribution, and *after* advisory
  evidence construction. **Selected.** The receipt retains
  `expected_graph_revision`, never whatever revision is observed later.

## Proof and scope

`tests/test_v2139_independent_evidence_preimage.py` uses the existing
real ProgramGraph and SourceDocumentSession fixture and injects changes
during the existing `_independent_change_lines` mapping. It verifies:

- a normal review still returns an importable receipt from one evidence pass;
- reentrant live editor update and external disk replacement refuse review;
- graph revision change during evidence refuses instead of mislabeling proof;
- a compiler failure concurrent with graph mutation reports an ownership
  conflict rather than naming a speculative invalid source function;
- late changes during import refuse *before* ProgramGraph.edit_many.

No extra parser, mutable evidence cache, source writer, graph owner, compiler
pass or ADR. The original `_independent_functions_plan` and
`_qualified_source_edit_plan` remain the only owners. Other source/graph
reconciliation contracts and ordinary invalid Python buffer handling are
unchanged. Rollback to v2.138 if qualification reveals unexpected refusal.

GitHub headless and native-Qt CI are early gates, not substitutes for the
independent Linux Mint host report.
