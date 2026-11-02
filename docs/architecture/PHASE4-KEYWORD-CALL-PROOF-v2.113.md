# v2.113 — keyword-call correspondence in source-owned Python

## Problem and architecture choice

Independently authored Python often calls functions with named arguments. Studio's graph compiler emits positional arguments for existing graph-owned call nodes and its reverse proof only understood those canonical forms. Rejecting an otherwise equivalent named call forced developers to rewrite source they own.

**Rejected alternative:** add a separate keyword-to-graph converter or change the source document to canonical positional syntax. Either creates another semantic owner and risks discarding source formatting and intent.

**Adopted:** within the existing `_independent_functions_plan`, copy only explicitly selected AST function regions and normalize strictly qualified calls in a *temporary compiler candidate*. A call is eligible only when the callee is an unshadowed, exact graph-owned function with the same source signature, positional arguments form a prefix, and every remaining named argument is a local `ast.Name` with exactly the required formal parameter name. A target outside the selected import must have unchanged graph-owned AST source. All local-name reads are side-effect-free, so reordering keyword spelling does not reorder effectful evaluations. The original source AST remains unchanged and supplies review evidence.

The existing `_qualified_source_edit_plan`, full graph trial lowering, current `SourceDocumentSession` revision/SHA and `ProgramGraph.edit_many` remain the only authority to accept a change. The generated-source workflow stays byte-exact. Calls with effects in their argument expressions, `*args`, `**kwargs`, defaults, duplicate/unknown arguments, or missing/ambiguous/rebound callees are refused, not guessed.

## Tests and qualification

`test_v2113_keyword_call_reconciliation.py` verifies positional/keyword mixtures, reordered keyword positions, unchanged semantic calls, exact source-argument spans, effectful call nodes, atomic import/undo, rejection on callee changes, shadowing and unsupported syntax, stale revision, and generated-source strictness. Existing v2.101–v2.112 compiler and release suites must still pass. Linux native Qt qualification is required before promotion and cleanup.

## Non-goals

This does **not** import new functions, call sites, changed call targets, signatures, nonlocal variable semantics, arbitrary Python AST, or source text mutation. Python is the first language adapter, not a justification for a universal mutable project graph.
