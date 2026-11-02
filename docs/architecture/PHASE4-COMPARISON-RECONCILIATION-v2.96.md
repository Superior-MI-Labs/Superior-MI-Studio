# v2.96 | Proven comparison edits and scoped diagnostic refusals

## Problem and design decision

The existing graph/compiler already supported `python.less_than` and `python.equal_int`, with identical canonical `py:int` input and `py:bool` output ports. Source reconciliation only considered the add/subtract/multiply family, even when the source edit was a safe typed comparison substitution. Meanwhile, independently-authored multi-function review returned a whole-candidate error without identifying the invalid function.

Two approaches were considered: (A) build a general AST-to-graph matching or diff engine; (B) extend the existing `_qualified_source_edit_plan` to handle only proven same-port operation substitutions, and use its same compiler proof to isolate invalid explicitly selected regions on the error path. **B is adopted.** A second AST interpretation engine would violate compiler/source-of-truth discipline.

## Implemented contract

- In source-owned edits, only single `a < b` and `a == b` comparisons assigned to the existing mapped generated variable may change an existing `python.less_than`/`python.equal_int` graph operation. All nodes, ports, execution/data edges, graph identity, and layout remain unchanged.
- The mapped operation must pass `ProgramGraph.replace_node_operation` with *exact canonical* port compatibility. The entire trial ProgramGraph must then lower to the candidate Python AST, or byte-exact generated source for strict generated-file import. Both remain preconditions to a single edit transaction.
- Chained comparisons, `<=`, `!=`, string comparators, new statements, reordered operations, incompatible types, signature changes and unknown AST constructs are not new supported syntax. They fail closed.
- Independently-authored multi-function review still requires 1–32 distinct, explicitly named top-level functions in one source session. Its original whole-batch proof runs first. Only if it fails, re-run that *same compiler preflight* for one selected region at a time to name the first refusing function and its source line range. This diagnostic cannot approve any subset or modify either owner.
- Source and graph revisions and exact source SHA-256 are checked again at import. The source owner retains all text, including opaque unrelated statements. The graph owner handles one undoable transaction; nothing is automatically published or executed.

## Verification and non-goals

Regression tests cover exact source preview/review/import, reverse comparison edits, nested conditional branches, typed port and edge identity, undo/redo, independent sources with extra imports/helpers, unsupported and chained comparisons, and scoped refusal diagnostics in multi-function edits. Native Qt remains a separate host gate; this release changes the compiler and reports, not the core Qt widget topology.

Do not expand this into general comparison operators, source rename inference, speculative function matching, or a generic Python parser. Future source/graph reconciliation should add capabilities only where the existing compiler can prove exact equivalence and preserve the source editor's authority.
