# v2.145 — Linked-source receipt checks the graph after external inspection

## Reproduced ownership gap

`LinkedPythonSource._qualify_receipt` checked that the current ProgramGraph
revision/fingerprint was compatible with the accepted link, then inspected
the source owner's on-disk preimage. `SourceDocumentSession.inspect_external`
can invoke reentrant callbacks during tests or integration. If such a
callback advanced ProgramGraph, the link could return a disk hash after
accepting a graph identity that was no longer current. In a no-op
`import_edits`, the caller could then stamp `link.graph_revision` with
the **new** graph revision without any compiler proof. During a real
import, it could report an obsolete error or accept a source-only no-op
from changed graph state.

## Alternatives and decision

- Snapshot graph state in an independent cache or add rollback when
  no-op receipts are stale. Rejected: extra source of truth, unnecessary
  state changes and brittle undo semantics.
- Reuse the existing linked-source receipt owner. Capture the actual
  ProgramGraph revision on entry to `_qualify_receipt`, retain its existing
  content fingerprint check (which intentionally allows undo/redo back to
  identical graph state), and refuse if that revision advanced during
  source inspection. Selected. The original source/disk baseline,
  `_assert_current_source` gate, compiler and graph writer stay unchanged.

The new post-inspection revision check protects both
`LinkedPythonSource.review_edits` and `import_edits`, including no-op
paths, without another compiler pass. It is a bounded reentrancy guard,
not a global multithreaded document lock.

## Evidence

`tests/test_v2145_linked_graph_inspection.py` uses the existing
ProgramGraph and SourceDocumentSession owners. Seven tests cover:
normal no-op review/import; graph mutation during no-op review and
import; graph mutation in final inspection before an actual source edit
could reach ProgramGraph.edit_many; source-trivia-only no-op import;
a valid authored literal import; and the intentionally supported
undo-back-to-identical-fingerprint navigation.

No new registry, document snapshot, compiler, writer or ADR.
Rollback to v2.144 if a supported linked-source flow regresses.
GitHub headless/native Qt CI and Linux Mint host qualification remain
separate gates.
