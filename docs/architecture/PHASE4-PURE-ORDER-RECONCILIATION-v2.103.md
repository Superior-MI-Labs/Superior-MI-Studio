# Phase 4 v2.103: Pure assignment dependency order

## Problem and two approaches

A source rewire can change the order in which `_preview` generates numbered values, even while all graph identities remain stable. Prior imported-source proof required matching Python statement position, so this change was refused despite valid graph topology.

1. **Rejected:** introduce a second persistent source/graph map, or treat arbitrary Python AST statement order as irrelevant. Both bypass the existing compiler or risk silently reordering side effects.
2. **Implemented:** preserve `ProgramGraph` and the existing node-line receipts. For explicitly selected independently authored functions, pair original assignments by exact function/target identity; use stable graph node IDs to alpha-align temporary names in trial lowering; permit only reordering inside a contiguous sequence of non-effectful, dependency-valid generated assignments. Then require full AST equality of the normalized proof.

## Non-negotiable limits

- No calls, division or modulo, effectful operations, local assignment effects, control-flow reordering, branches or Return moves are admitted by the ordering exception.
- Both candidate and compiler-emitted pure runs must define values before referencing them. Duplicate generated targets refuse.
- A generated-source dialog import retains byte-exact output requirements. The more flexible proof is only for explicitly selected, independently authored function regions.
- Source buffers, whitespace, comments, unrelated functions and original files are not written by graph reconciliation. No persistent AST/value index is introduced.
- The graph still passes complete validation and Python lowering after trial commands; source revision/SHA and graph revision are checked at import; changes are a single undoable graph transaction.

## Qualification

`tests/test_v2103_pure_order_reconciliation.py` covers graph/node identity, a genuine dependency-creating input change, reordered source values, generated-source refusal, forward references, division and call barriers, duplicate targets, undo/redo, unchanged independent text, and stale revision rejection. The release still needs native Linux Qt qualification.
