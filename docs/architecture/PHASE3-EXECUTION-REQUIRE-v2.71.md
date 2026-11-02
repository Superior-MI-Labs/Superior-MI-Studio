# v2.71: Bounded execution effects — first sequential Require

## Evidence and authority

Baseline v2.70 has 840 local headless checks; v2.69 is the latest confirmed
WolfCat-Studio native Qt baseline. v2.70 host qualification is still pending.
`ProgramGraph` remains the only editable graph document. Its existing canonical
`NODE_TEMPLATES` defines port structure, while `python_lowering.py` alone owns
qualification and Python AST generation. Preview never executes; publication
uses the existing guarded source writer and requires a saved graph revision.

## Alternatives and decision

1. Implement general mutable variables and loops with a new graph runtime now:
   rejected. Without dominance, effect ordering, assignments, and loop-carried
   state qualification, general execution would be unsound.
2. Add special-case branches into the GUI/source generator: rejected. Would
   duplicate semantics and let UI interactions masquerade as Python semantics.
3. Extend the existing structured execution tree with a sequential Require
   effect: chosen. It proves effect ordering, explicit control pin wiring,
   failure behavior, source mapping and publication without expanding to a
   second compiler or arbitrary cycles.

## Semantics

- `python.require@1` has required `exec:execution` and
  `condition:py:bool` inputs plus `then:execution` output.
- It executes *only* when reached along its explicit control edge; it
  advances on true; on false it raises `ValueError` using a stable
  generated `if not condition: raise ValueError(...)` statement. This is
  unaffected by Python's `-O` optimization (unlike `assert`).
- Structured execution remains an acyclic tree: one Entry, optional
  Branches and Require nodes, one Return Flow per leaf, no joins, loops,
  or disconnected effect nodes. Every Require has exactly one parent and
  connected continuation.
- Pure Boolean producers are lowered before the Require at the point they
  are needed, along the active path. Execution, effects and graph layout
  cannot be reordered by UI positions. Graph IDs map to exact source lines.
- Pure `python.call` cannot invoke a function that may Require (including
  transitive calls). Effects must not be speculatively hoisted as expression
  producers. Calling effects requires a future explicit execution-call contract.
- User names that shadow `ValueError` cause qualification refusal. Incomplete,
  unsupported, or invalid execution graphs remain saveable, never executable.

## Tests and limits

- `tests/test_v271_explicit_require.py` verifies runtime true/false behavior,
  multiple ordered effects, missing control paths, wrong types, forbidden
  effect calls, source identity, save/reopen, undo/redo, and guarded publication.
- `scripts/program-graph-python-gate.py` verifies the persisted example
  `examples/qualified-guarded-branches.smi-graph` without executing it.
- `studio_native/qt_smoke.py` has a new ProgramGraph stage for template creation,
  preview, publication, and persistence. Only WolfCat-Studio can close it.
- Still not qualified: mutable assignment/getters, loop backedges, control
  joins, external IO, effectful calls, full bidirectional source reconciliation.

Next: define a versioned mutable-variable effect contract with explicit
read/write dominance and loop-carried state before implementing loops.
