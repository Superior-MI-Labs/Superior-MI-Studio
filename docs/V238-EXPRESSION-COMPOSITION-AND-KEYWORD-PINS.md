# v2.38 — Composable constant expressions and explicit keyword call pins

## Qualified native baseline

The user-provided v2.37 report (`qualification-20261029-170354-251513.tar.gz`) contains `NATIVE_QT_SMOKE_PASS` and 477 passing headless tests. v2.38 continues from that exact packaged source. Qt itself is **not available** in the build environment, so v2.38's GUI changes remain a host qualification gate.

## One semantic graph, one source-edit authority

This change expands the existing Python AST projection (`python_graph.py`) and `rewire_source_operand()` (`python_edit.py`); it introduces neither a new graph serializer nor a second Python code emitter. `source_connection.inspect_connection()` still returns the exact candidate from `rewire_source_operand()` used for final user review. All edits still pass `_validated_proposal()`, followed by the existing stale-file check, create-only backup, and atomic replacement on explicit approval.

## Named keyword call inputs

Function-scope `ast.Call` nodes now project every explicit `keyword=value` as its own **named input** `kw_<keyword>`. The expression producer supplies the corresponding value edge. Literal and parameter outputs can be wired to an actual `keyword=value` operand, not just `arg0`/`arg1`. AST names, rather than displayed pin labels or raw string concatenation, determine exactly which keyword is changed. `**kwargs` unpacking can appear as a read-only `** unpack` input, but can never receive a sourced rewrite under this contract. `*args` remains unsupported for call-source rewrites. The CALLEE node continues to mark dispatch/effects as unverified. Python can bind keyword values differently at runtime; validation here proves the *source transformation* is well formed, not that a dynamic call will succeed.

## Bounded constant-only expression results

Operator and comparison result ports can now serve as source endpoints **only** when the actual AST confirms a bounded, effect-free expression tree. Allowed: primitive numeric/string constants, bounded numeric `+`, `-`, `*`, bounded string `+`, numeric unary `+`/`-`, and one primitive-only equality/order comparison. Refused: variable reads, overloaded operators, calls, attributes, indexing, short-circuit logic, division, chained comparisons, deep or large literals, and connecting an expression into its own source range. No AST expressions are evaluated during qualification.

The lowering copies the parenthesized source expression into the destination operand. This is **not a live mutable wire**, an alias, or an SSA dependency; it is a requested source transformation that the next parse reconstructs as ordinary graph nodes and edges. It is only allowed for expressions whose duplicate evaluation has no user-observable side effects under the restricted primitive whitelist.

## Interaction and validation

The existing green/amber source connection preview and the actual drop invoke the same adapter preflight. A wire can preview safely but still be refused on save if the source file changes externally. Each accepted edit must be reviewed before atomic save. The new example file `examples/python-v15-expression-keyword-connections.py` exercises explicit named keyword inputs and constant-only arithmetic/comparison outputs.

**489/489 headless tests passed**, up from 477. Twelve targeted tests cover keyword edges, value identity, AST round trips, constant arithmetic/comparisons, rejection of unverified expressions and unpacking, self-connections, source bytes, Unicode/CRLF, and stale-write rejection. Native Qt `qt_smoke.py` now exercises keyword/constant preview, Qt canvas ownership, and unchanged source, and captures `expression-keyword-wiring.png`.

## Patch plan (next milestones)

1. **Native gate**: Qualify v2.38's named keyword pin rendering and source preflight against real Qt using `RUN-ALL.sh`, with screenshots and failure report retained.
2. **Operation definitions and pin typing**: Finish canonical adapter-owned creation/connection descriptors and versioned capabilities; prevent visual templates from advertising unqualified Python authorship.
3. **Typed expression composition**: Expand source-backed wiring to *verified* producer expressions with dominance/effect analysis, not mere copied text. Distinguish data dependency from copyable literal expression and explicit execution effects.
4. **Function interface**: Standardize Entry parameter and Result return contracts; formalize function signatures/call sites together and support only reviewed, AST-qualified changes.
5. **Universal workspace**: Remove remaining window-global source/resource aliases after independent-view Qt behavior is qualified. Keep one graph renderer and no duplicate parser.
6. **Cross-adapter round trips**: Test code→graph→reviewed source edits→graph for increasing Python coverage, then require another language adapter to satisfy the same contract before announcing multi-language creation.

### Known boundaries

This release does not support arbitrary operator-result wires, runtime type checking, execution-edge authoring, keyword unpack rewrites, or live graph execution. User code is **never executed** for inspection. It is intentionally conservative when Python's dynamic semantics cannot be proven statically.
