# Phase 4 v2.102: Compiler-proven semantic input reconciliation

## Decision and alternatives

**Selected:** Extend the existing authoritative Python compiler's source-review plan and the graph owner's `replace_input` transaction to other already modeled, uniquely identifiable input ports. No new parser, graph identity store, source owner or tab behavior.

**Rejected:** A general AST-to-graph expression builder or arbitrary source diff that invents nodes or tries to preserve layout by inference. This would add competing semantic authority and could silently change control/data behavior.

## Implemented boundary

- Existing arithmetic/comparison rewiring is joined by unary Boolean Not, eager typed Select, pure graph-owned function-call positional arguments, and pure/structured Return values.
- A changed source operand must be an `ast.Name` corresponding to precisely one previously emitted value in the same graph function. The graph node's existing input pin must have exactly one occupied wire.
- Pure function-call name and argument count must match its graph-owned callee signature; only already-existing call argument *wires* are changed. Execution calls and dynamic Python calls remain unqualified.
- For independent source-file review, unchanged Return statements are aligned only after verifying the baseline/edited Return counts. This is not a persistent source map. The complete trial graph must lower to the entire candidate AST, preserving source-owned unrelated statements, and the current graph and source revisions remain authoritative.
- Generated-source review uses **byte-exact** final comparison. It refuses otherwise plausible rewires whenever the graph compiler emits a different assignment order; this is an intentional safety limit, not an invitation to skip proof.
- A change that would orphan any existing graph node, modify execution structure, create cycles, change port types, alter effect timing, or depend on unknown values refuses atomically; the source file and graph remain unchanged.

## Tests and promotion

`tests/test_v2102_semantic_input_reconciliation.py` exercises generated and independently authored source, multiple simultaneous pin rewires, exact input identities, undo, retained source comments, structured Return and negative topology changes. Full headless doctor and the ProgramGraph/Python-first gates, archive validation and isolated Linux installation are release requirements. WolfCat-Studio native Qt PASS is still required to promote v2.102 and trigger old-version cleanup / auto-launch.
