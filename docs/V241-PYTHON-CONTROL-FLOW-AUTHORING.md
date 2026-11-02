# v2.41: Python-first control-flow authoring and language-neutral capability descriptions

## Why this change

A language-independent visual renderer must never hardcode Python syntax, Python scope rules or source-edit effects into shared nodes. `authoring_contract.py` owns only versioned operation capability descriptions, with a duplicate/malformed capability check. `python_authoring.py` remains the *only* language-specific lowering authority. The existing AST/source editor, graph producer, contract validator, diff review and atomic replacement are unchanged.

## Newly qualified actions

- `python.conditional-return-from-pass.v1`: choose a declared input, a comparison operator, primitive comparison constant, true return value and false return value. Creates one Branch and two explicit source Returns.
- `python.for-range-accumulate.v1`: choose a declared parameter and fresh loop/accumulator names. Creates local binding, `for ... in range(parameter)`, an update statement and Return.
- `python.while-countdown.v1`: choose an input parameter and two fresh locals. Creates a local copy, a loop progression, and Return without rebinding the input.

All work from qualified standalone `pass` placeholders of synchronous undecorated functions; can be initiated from a searchable library, right-click search or a compatible parameter output. A pin-drop uses the exact source parameter and scope identity; it does not offer a general-purpose connection or invent execution-order safety. AST checks compare the created statement suite with the intended source construct, plus unaffected function statements. Signed numeric primitives are recognized without admitting general expressions.

## Qualification boundaries

- Accepted only as **source generation proposals**, not arbitrary node drawing or execution.
- Undefined dynamic values/types, monkey-patched `range`, arbitrary closures, decorators, async functions, nested control or cross-module edits are not qualified.
- All parsed graphs must use the existing validated control/data interfaces. The source remains the sole authority after approval.
- Python-first gate now constructs a multi-function program *from blank* with Branch, For and While and compares its graph to an equivalent text-authored Python program. That is still not a full Python readiness gate.
- Native Qt qualification (new Node Library entries, pin-drop, tab ownership and source preview non-write) is required on WolfCat-Studio. Do not claim GUI PASS without the host report.

## Follow-on large patch plan

1. General connected visual authoring: operations as composable graph edits, not a growing collection of isolated templates; add source-backed dataflow/control-flow validation before accepting arbitrary wires.
2. Function interfaces: Entry/Result, positional/keyword defaults, call-site propagation and multiple returns with explicit stale/ambiguous refusal.
3. Multi-function interactive acceptance: user builds real Python programs from blank via node creation and wiring, and edits them in text; evaluate graph/code parity, undo/redo and coverage.
4. Universal workspace consolidation, native Qt polish and performance. No second language adapter before the comprehensive Python-first review and user-requested features are ready.
