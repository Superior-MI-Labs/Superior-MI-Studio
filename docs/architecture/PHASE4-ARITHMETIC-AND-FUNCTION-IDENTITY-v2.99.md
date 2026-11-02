# v2.99 — Arithmetic adapter consolidation and independent function identity

## Evidence and options

The v2.98 host archive `qualification-20261102-044314-48735.tar.gz` confirms the entire Qt smoke and doctor passed. Reconciliation's source importer maintained a duplicate arithmetic operator table and recognized only `ast.Constant` literal edits. Python parses a negative integer such as `-17` as `UnaryOp(USub, Constant(17))`, so graph-supported negative literals were not reversible from independent source.

- **Rejected:** a new general AST importer, expression evaluator or mutable source-to-graph mapping. This would create a second semantic authority, permit unsafe or ambiguous translations, and expand maintenance cost.
- **Chosen:** one `INTEGER_ARITHMETIC_AST` adapter table for generation and reverse proof, plus an exact bounded negative integer literal normalization that still requires a byte-exact/whole-AST compiler trial before any edit.

## Actual implementation

`program_graph.NODE_TEMPLATES` owns the identical input/output port schemas for integer add, subtract, multiply, floor divide, and modulo. `python_lowering.INTEGER_ARITHMETIC_AST` owns corresponding Python syntax; the compiler and both generated/independent source reconciliation consume the same table. The resulting Python uses ordinary signed `//` and `%` behavior and raises `ZeroDivisionError` naturally when appropriate; Studio does not silently override Python semantics.

Only `Constant(int|bool)` or `UnaryOp(USub, Constant(int))` are considered literal candidates; Boolean coercion, arbitrary unary calculations, floats, exponentiation, division `/`, and matrix multiplication remain unsupported. Trial `ProgramGraph.edit_many` and complete Python lowering prove the result before atomic import. Graph layout, edges, identities, source text, and file ownership remain unchanged.

Explicit independent top-level function names remain the sole matching key. Missing names report the real source's visible function names (bounded to 12); duplicate names report exact definition lines. This is diagnostic only, not implicit rename support. The complete source SHA, graph/source revision, disk inspection, and trial compiler remain required at commit.

## Qualification

`tests/test_v299_integer_arithmetic_reconciliation.py` exercises five-operation interface parity, both new operators in generated and independent-source round trips, negative operands, zero division, undo/redo, source-line receipts, atomic batch refusal, exact function identity conflicts, and unsupported syntax. Full headless suite and archive integrity are mandatory for release. Native Linux Qt PASS on WolfCat-Studio is required for promotion and old-install cleanup.
