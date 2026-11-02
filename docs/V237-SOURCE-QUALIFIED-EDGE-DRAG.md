# v2.37: Python source-qualified edge drag

## Why this patch

Previously the user could drag an output to almost any visible source input. The UI rendered a line, but only after release did `rewire_source_operand()` decide whether Python source could express it. That made the visual programming interface look more capable than the adapter. Separate boundary and ordinary-port branches also had duplicate UI glue, complicating future authorization.

## Single authority

`source_connection.inspect_connection(doc, source_node, source_port, dest_node, dest_port)` locates the common exact Python function and calls **the existing** `python_edit.rewire_source_operand()`. Its returned `ConnectionCheck` includes a real immutable `EditProposal` when successful, not a fabricated edge. The preview never writes source or changes the graph.

The drag UI resolves function boundary mirrors via the already-qualified `terminal_return_target()`, then uses the same check. It displays a green ring for source-expressible target inputs, amber on a refused hovered input, and a reason in the status bar. Up to 24 visible inputs are preflighted at drag start, with further destinations lazily checked once on hover; no per-mouse-move AST compilation. The cache is transient, discarded at the end of the gesture.

On release, compatibility is re-evaluated in the active source context; a successful proposal is sent through the existing diff-review and backup/atomic save path. `NativeLab.rewire_python_input()` delegates to this authority as well. Draft graph nodes continue using their separate existing prototype connection editor.

## Explicit boundaries

This does **not** enable arbitrary wiring, prove Python runtime dispatch/effects, or dynamically connect values. It enables visual proposal of the same supported source rewrites already recognized by the Python adapter. A connection may pass a preview and fail later when the user modifies the source file externally; `apply_proposal()` intentionally revalidates disk contents and refuses stale writes.

Current supported sources: source-backed literals, function parameters and conservatively dominated local assignment values. Current destinations: exact editable operands in supported ordinary expression, call, assignment and Return nodes. Execution-flow rewiring, call-result copying, unsupported lexical scopes and ambiguous/early function-return boundary edits are refused.

## Regression evidence

Nine headless tests cover no-write preflight, exact proposal identity, a real approved call-argument reparse, already-connected targets, invalid pins, cross-function scope, unsupported call results, stale external changes and GUI contract alignment. Full suite: **477/477 PASS**. Native Qt drag-preview and canvas paint tests were added to `qt_smoke.py`; **host result pending**.

Next: improve real connection UX using grouped searchable compatible operations and expand the source adapter's verified connection and expression lowerings. Avoid adding free-form edges to a source-backed graph before they are source-expressible.
