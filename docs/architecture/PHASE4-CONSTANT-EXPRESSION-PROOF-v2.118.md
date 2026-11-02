# v2.118 — Compiler-proven constant expressions in independently authored source

## Problem and decision

The graph already stores typed integer literals, but independently authored Python often spells them as expressions such as `2 * 7` or `(2 + 3) * 4`. Studio's generated-Python importer must remain exact, while the independent-function importer can admit additional syntax *only if* the full existing graph compiler proves the same program.

Two approaches were considered: (1) create expression graph nodes or a second Python evaluator/parser for these inputs; rejected because it duplicates graph/compiler ownership and can execute untrusted syntax. (2) add a narrow, transient AST canonicalization inside the already-owned `proof_function`; adopted.

`CanonicalLocalSyntax` visits existing source AST only in an in-memory copy, folding integer constants with `+`, `-`, `*`, nonzero `//` or `%` and unary `+`/`-`. It never invokes `eval`, a user function, a file read, or an external runtime. Both operands and results must have exact `int` type (never `bool`) and magnitude ≤ 2**63 - 1. Python's signed floor/modulo semantics are used. Fixed bounded integer comparisons (`<`, `<=`, `>`, `>=`, `==`, `!=`) and fixed Boolean `not`/`and`/`or` are similarly admissible only when every operand is a statically known constant of the exact expected type. Chained comparisons, dynamic expressions, float, shift, power, call, unknown name, bool/int coercion and zero-divisor operations are not normalized. Malformed or unsupported syntax ultimately refuses through the existing compiler. No symbolic algebra or speculative structural correspondence is attempted.

This is **proof normalization, not publication**: no additional graph operations are created, source text and comments are retained byte-for-byte, and an edited value imports only through the existing `ProgramGraph.set_property` command after full compiler re-lowering, source revision/digest, graph revision, type and atomicity checks. Equivalent arithmetic with no resulting graph change is source-owned. Generated-source import remains strict.

## Regression evidence / limitations

`tests/test_v2118_boolean_expression_proof.py` validates fixed Boolean comparisons, signed numerical semantics, source-only no-ops, undo, and refusal of dynamic or effectful candidates. `tests/test_v2118_constant_expression_proof.py` tests real graph functions, negative modulo/division, nested expressions, read-only Inspector evidence, annotated readable locals, source-only docstrings, local undo/redo, repeated/stale qualification, external file changes, loop/repeat preservation and explicit refusal of raising/effectful/oversized operators. This does not make arbitrary Python expressions graph-editable, nor is dynamic constant propagation or source expression identity persisted.

Native Qt qualification on WolfCat-Studio remains required for promotion.
