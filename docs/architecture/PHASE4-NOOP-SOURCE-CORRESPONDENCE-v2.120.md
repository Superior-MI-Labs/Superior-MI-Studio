# v2.120: bounded source-only no-op syntax

## Decision
Use the existing one-way, transient AST normalization inside
`_independent_functions_plan`, not a new editable source model, second
source-to-graph importer, or code-rewrite pass. Continue to require complete
`_qualified_source_edit_plan` proof before accepting any graph edit.

## Changes
- Allow bare builtin annotations only when their target is already assigned
  in the selected function or is an explicit graph-owned parameter. These
  annotations are not runtime operations in Python function bodies.
- Permit pass-only `if` statements where the test has become an exact,
  statically proven `bool`. Refuse evaluating or discarding dynamic,
  potentially effectful guards. No automatic deletion of empty suites.
- Keep the source bytes, graph identities, typed ports, atomic graph
  transactions, revision checks, and strict generated-source dialog intact.

## Non-goals and failure policy
Do not infer novel graph nodes from annotations, accept arbitrary typing
expressions, erase dynamic condition evaluation or special-case errors into
success. Full semantic re-lowering remains the authority.

## Proof
`tests/test_v2120_independent_noop_correspondence.py` exercises source-only
no-edits, combined existing-call input swaps, source preservation, graph
undo, negative cases, branch-local edits and stale revisions. Native Qt on
WolfCat-Studio remains a distinct promotion gate.
