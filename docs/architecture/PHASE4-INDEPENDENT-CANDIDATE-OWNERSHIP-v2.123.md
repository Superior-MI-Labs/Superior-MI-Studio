# v2.123 — independent-source candidate ownership consolidation

## Decision and rationale

The prior implementation nested approximately 175 lines of transient
independent-function source transformation inside the batch reconciliation
planner. That made it harder to reason about where source-only trivia,
compiler-generated local identities and keyword syntax were normalized.
This was not evidence for a new parser, source map or compiler framework.

Two approaches were compared:

- **Rejected:** extract a standalone reconciliation service or generalized
  AST adapter. It would duplicate `python_lowering.py`'s admission contract
  and create unnecessary API and maintenance costs.
- **Chosen:** leave graph/source owners, whole-graph trial proof, source/graph
  revision gates, and imports untouched. Extract focused *private functions in
  the same module* for ephemeral source function preparation, uniquely
  proven generated local correspondence and keyword syntax normalization.

The batch planner remains the sole orchestrator of selected top-level
function identities and compiler proof. Generated-source imports keep strict
byte-exact source admission. None of these helpers authorizes a graph edit.

## Proof obligations

- The independent source `ast.FunctionDef` is deep-copied before any mutation.
  Original `SourceDocumentSession` text, file bytes, comments and formatting
  remain unchanged.
- Local spelling changes require the existing single/multiple unique identity
  matching with scope and duplicate-binding refusals; ambiguous producers
  cannot gain inferred identity.
- Keyword calls may become positional in a temporary candidate only for
  exactly named parameters and Name-only local operands. Any other syntax is
  left to the existing full compiler to reject.
- Compiler stage must still reproduce the entire supported graph and must
  reject unsupported operations, stale source revisions and partial imports.
- Application, navigation and Qt interactions are unchanged in this patch.

## Evidence and exit gate

New focused `test_v2123_independent_candidate_boundaries.py` plus the existing
source reconciliation, source-owner, generated-import, release and headless
qualification suites. Full native Qt on the end-user Linux host remains a
separate promotion gate. `docs/agents/NEXT-TASKS.md` continues as the only
active implementation queue; this file records a design decision, not a
second work order.
