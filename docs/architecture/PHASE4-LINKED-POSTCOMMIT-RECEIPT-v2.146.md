# v2.146 — Linked-source post-commit receipt refresh is all-or-refuse

## Existing failure path

`LinkedPythonSource.import_edits` commits a qualified graph transaction
through `ProgramGraph.edit_many`, then immediately advances the accepted
link's graph revision, graph fingerprint and source revision **before**
calling `preview_python` to refresh its generated baseline. A failed
preview, an unqualified preview returning `None`, or a reentrant graph,
editor or disk change during preview could leave the link carrying a
partially updated set of ownership receipts. A subsequent review could
wrongly interpret the old baseline under a newer graph revision.

## Alternatives

- Undo graph edits when post-commit projection fails. Rejected: graph undo is
  a separate user-owned edit and might overwrite unrelated legitimate work;
  a rollback shim would violate source-of-truth discipline.
- Move post-commit projection into a new controller/receipt service. Rejected:
  duplicates the existing `LinkedPythonSource` and compiler owners.
- Qualify all next receipt fields in the existing `import_edits` method
  before assigning any accepted metadata. Selected. Compute a generated
  baseline and fingerprint for the committed ProgramGraph, then verify
  that graph revision, source revision/text/saved bytes and external disk
  inspection remain the same. Refuse if any differ. Only then advance
  the existing receipt fields and return the graph edit result.

The single ProgramGraph transaction remains authoritative and is **not**
automatically reversed if receipt refresh fails. A refused refresh leaves
the link's previous accepted state intact, requiring explicit reconciliation
or relinking rather than claiming to have accepted the new revision.
The source document is never rewritten by this import path.

## Tests

Eight regression cases in
`tests/test_v2146_linked_postcommit_receipt.py` exercise ordinary
two-step import, refused preview error, rejected unqualified baseline,
late live editor or disk changes, graph changes during postcommit preview
or graph fingerprint construction, and source-trivia-only import.
They verify that a failure after the graph writer leaves all link receipt
fields unchanged, even though the graph edit itself remains committed.

No new parser, second graph/document authority, duplicate source writer,
rollback operation or ADR. GitHub headless/native CI are separate from
Linux Mint native host qualification. Rollback to v2.145 if needed.
