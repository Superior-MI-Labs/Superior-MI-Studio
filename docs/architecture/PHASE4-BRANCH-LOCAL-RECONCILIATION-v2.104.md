# v2.104: suite-scoped pure source-order reconciliation and qualified release build

## Architectural decision

Extend the existing independent-source compiler equivalence proof, not the
ProgramGraph owner or the Python AST source owner. v2.103 recognized a changed
pure dependency order only in the top-level function body. That same narrow
case can occur inside compiler-emitted structured branches and loops. The
reconciliation equivalence normalizer now operates within **each execution
suite separately** (function, if/else, nested if, for/while bodies and else
arms). It sorts only contiguous simple assignments to unique `_smi_value_*`
names when their AST expressions are pure and already defined before use.

It **never** moves an assignment between suites, across a return/call/effect,
or across a potentially raising division/modulo, and does not normalize
try/with/match or arbitrary user code. Dependency safety is checked in both
baseline and candidate sources. After this advisory equivalence check, the
existing trial ProgramGraph and whole-Python lowering must still prove the
entire candidate. The source remains unchanged and the graph commits an
explicit atomic, undoable batch only after source revision/hash and graph
revision are rechecked. Generated-source dialog imports remain byte-exact.

## Rejected alternatives

- General AST canonicalizer: could silently reorder effects or change Python
  evaluation behavior and would duplicate the compiler's semantics.
- New persistent source/graph identity database: creates a second authority
  and requires synchronization with source revisions and undo history.

## Release pipeline consolidation

`scripts/build_release.py --qualify-headless --output PATH` now calls the
**existing** agent headless gate and builds the exact deterministic manifest-
verified archive only after PASS. A failing gate cannot publish a new ZIP.
The existing separate native Qt host qualification is unchanged and remains
mandatory before managed-install cleanup and interactive launch.

## Evidence and limits

- `test_v2104_nested_pure_order.py`: nested/else/for/while normalized suite
  proofs, no crossing branches/effects, forward reference, duplicate target,
  division and function call refusal.
- `test_v2104_nested_roundtrip.py`: real compiler branch-local wire edit,
  read-only review, unchanged independent-source bytes, one atomic import,
  undo/redo, invalid forward reference and strict generated import refusal.
- `test_v2104_qualified_release.py`: one existing gate, no artifact after
  failed qualification, and no overwrite of a previously built archive.

Passing headless tests does not claim v2.104 native Qt qualification.
