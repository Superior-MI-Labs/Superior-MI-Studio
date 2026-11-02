# ADR: One module binding witness per independent source batch (v2.110)

## Context

Multi-function source review could select up to 32 function regions, but the
static module binding guard walked the same independently authored AST once
per selected function. This inflated qualification work and made it easier
for per-function guards to diverge. Source receipt indexing also walked the
Return syntax a second time after already collecting it.

## Alternatives

1. Keep independent per-name walks and add caching. Rejected: a redundant
   source identity map would be another invalidation point and would not
   consolidate the policy.
2. Run the existing conservative AST visitor once against the explicit
   selection map. **Adopted.** Collect sorted source-owner evidence separately
   for each selected identity; retain all existing compiler and revision gates.

## Contract

- Only exact, uniquely resolved, top-level named function AST nodes are
  eligible. The chosen definition is not counted as its own shadow.
- Module imports, assignments, decorators/defaults, class-body explicit
  `global` writes and other evaluated name-binding syntax remain conservative
  refusals. A declaration-only annotation does not bind a value, although
  its annotation expression may. No project Python is executed.
- Unknown dynamic effects remain outside the static proof; no claim of
  whole-program Python name-resolution correctness is made.
- A successful identity check does not authorize an import. Re-lower the
  complete trial ProgramGraph, compare the full qualified AST, re-check both
  document revisions, and commit once through ProgramGraph.
- Read-only source receipts use one AST indexing pass per function, with
  missing/ambiguous statement evidence omitted rather than guessed.

## Evidence

`test_v2110_module_identity_batch.py` tests multi-function single-pass
qualification, atomic undo, distinct simultaneous name shadows, bare vs
initialized annotations, evaluated annotation bindings, class/function locals,
wildcard imports, and the one-function route. Prior v2.109 tests cover
definition-time decorators/defaults and class-body `global` writes.
