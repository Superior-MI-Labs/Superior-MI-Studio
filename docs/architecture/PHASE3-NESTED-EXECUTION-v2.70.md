# v2.70: nested structured execution trees — architecture decision

## Baseline and evidence

v2.69 passed WolfCat-Studio host qualification on November 1, 2026
(`qualification-20261101-172948-8502.tar.gz`): 825 headless regressions,
Python-first, ProgramGraph Branch gate and all four isolated Qt stages.
v2.70 extends the same adapter; native host verification must be separate.

## Two implementation approaches

1. **Add special-case patterns for second and third Branch nodes.** Rejected:
   exponential case combinations and duplicate control qualification.
2. **Generalize the existing structured-Branch validator/emitter to an explicit
   execution tree.** Chosen: same ProgramGraph storage and Qt renderer, same
   `preview_python` and `publish_python` entry points, same Python AST backend.

## Semantic contract

- One Entry, one or more Branch nodes, one terminal Return Flow per tree leaf.
- Each Entry `then` and Branch `true`/`false` output connects once; every
  Branch/Return Flow has one incoming execution edge; no join, loop or cycle.
- Branch conditions must be qualified Boolean pure values. Return values must
  exactly match declared function return type. Unknown operations and effects
  fail closed. Direct local calls are eligible only when their complete called
  functions meet the same pure bounded lowering contract; no recursive calls.
- Data dependency graphs must be acyclic and contain no orphan operations.
  Producers for a decision are emitted before that decision; producers used
  by a Return are emitted along its selected execution path. Previously
  computed values are reused along dominating prefixes.
- Source-line maps enumerate the actual Python lexical statement traversal,
  not breadth-first `ast.walk`, which was incorrect for nested Returns.
- Graph layout, UI camera, and node positions cannot change source output.
- Failed preview or publication never executes code or destroys an incomplete
  saved graph. Publication remains the existing explicit guarded transaction.

## Qualification

`tests/test_v270_nested_control.py` covers both nesting directions, multiple
branches in both arms, behavior, source mapping, save/reopen, deterministic
preview, guarded publication, wrong types, cycles, joins, missing paths,
invalid properties and orphan nodes. `scripts/program-graph-python-gate.py`
validates the new persisted example and its output without executing it.

## Deferred work

General joins, mutable assignments, loops, effects, stateful operations,
bidirectional source reconciliation and IDE debugging still need explicit
semantics and independent qualification. Python remains the only language.
