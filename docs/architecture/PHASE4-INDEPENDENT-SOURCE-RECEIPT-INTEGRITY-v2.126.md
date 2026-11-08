# Phase 4: Independent-source receipt integrity (v2.126)

## Observed problem

Independent-function review validated the on-disk source only before the compiler proof. A source file or live `SourceDocumentSession` could change while that proof was running (for example through a reentrant host callback) without the review checking the resulting owner state. The import path also lacked a final disk check between a passing plan and the graph-owned edit. In those cases, the compiler's qualified AST and source hash were not necessarily attached to the same still-current source revision/disk preimage.

## Two considered approaches

- **A.** Create a new reconciliation snapshot/locking service and migrate both owners through it. Rejected: it adds another source-of-truth and broadens the change into thread/process control.
- **B.** Capture `session.revision`/`session.text` once in the existing `python_lowering` planner, use that immutable local evidence throughout proof, revalidate before issuing a review receipt and again before graph commit. **Selected.** This is deliberately optimistic conflict detection, not a process-wide file lock.

## Contract

- Read one text snapshot for UTF-8 size check, AST parse, original-source span collection and SHA256 receipt; keep all existing `ProgramGraph` compiler/transaction gates.
- After successful proof (or before explaining a failed compiler proof), reject changed source revision/text or on-disk preimage through the existing `GraphConflict` path. A separate final disk check protects the gap after the shared plan and before `ProgramGraph.edit_many`.
- Unencodable drafts refuse as `ProgramGraphError` without mutating either owner; source remains user-owned and recoverable.
- No claim of cross-process atomic filesystem locking; OS writes could still race with the last check. Never describe this as a saved-source transaction. External writes always require a separate guarded publisher.

## Evidence

`tests/test_v2126_independent_source_snapshot.py` adds six positive/adversarial tests. Existing source reconciliation, generated-source import, linked-source, and native Qt regression gates remain required. The change touches no Qt navigation ownership, no Python grammar admission, and no installer behavior beyond the version identifier.

## Next

Continue investigating any remaining linked-source conflict receipt duplication in `python_lowering.py`, then return to root-tab/navigation branch removal only after native parity proof. The canonical active queue remains `docs/agents/NEXT-TASKS.md`.
