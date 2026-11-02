# v2.36: Call creation and connected execution interfaces

## Host baseline

v2.35 passed the actual WolfCat-Studio Linux qualification report (456 Python tests, `NATIVE_QT_SMOKE_PASS`). v2.36 GUI changes have **not** yet been qualified by native PyQt6, which is unavailable in the packaging container.

## Decisions

- **One adapter authority**: `python_authoring.definitions()` advertises all eight qualified source transformations. `authoring_actions.available_actions()` serves the persistent Node Library, right-click search, and compatible output-pin drop. It does not create a second graph registry or text generator.
- **Two distinct call contracts**:
  - `python.call-return-from-pass.v1` creates `return callee(parameter, literal, ...)` from the exact standalone `pass` in a module-level function. Its Call output feeds Return's value pin.
  - `python.call-before-return.v1` creates `callee(parameter, literal, ...)` immediately before a direct Return. This is an explicit **effectful statement creation**, not a side effect inferred from a data connection.
- **Shared validation**: Both use the existing `_direct_statement`, `eligible_pass_targets` / `eligible_return_targets`, `_validated_proposal`, `_function_at_path`, and `apply_proposal`. Source is unchanged until reviewed and saved. Existing AST nodes are compared before/after generation; modified files are blocked by the atomic application gate.
- **Conservative identity**: Call targets are unique, non-decorated, synchronous module-level functions with one to four required positional parameters, no defaults or varargs, and no explicit ambiguous rebinding. The first argument is an existing caller parameter; remaining arguments are individually confirmed primitive literals. Nested caller scopes and incompatible pin IDs do not qualify. **Static identity does not guarantee purity, execution safety, type compatibility, or no dynamic rebinding.** The viewer never runs source while inspecting or generating proposals.
- **One existing CALL node**: A standalone simple call statement in the direct function body now has its existing argument/result ports plus normal execution input/output ports. A simple direct call feeding Return gets normal Entry → CALL → Return execution in addition to CALL result → Return value. The original CALL node is reused; there is no fabricated wrapper. Nested/lazy/keyword calls do not get speculative execution ordering. Control arms with unqualified effects keep the previous barrier and do not incorrectly infer joins.
- **Existing direct edges**: The preexisting `python_edit.rewire_source_operand` remains the only qualified edge-rewrite pathway for an existing positional call argument. v2.36 explicitly tests parameter → call argument → returned call result as a source round trip.

## User interactions

Open `examples/python-v14-function-call-authoring.py`, select **Source operations** in the library, then `Function Call → Return` or `Function Call → Continue`. Or right-click empty graph space, search `call`, and choose the eligible action. From a parameter output, drag into empty graph space to see only available connection-derived actions. Choose the function and any additional literal inputs; review the generated diff and explicitly approve the write. Reloaded source is reparsed into the same validated CALL, RETURN and data/control edges as text-authored code.

The Call → Continue action can execute the called function at runtime if the user separately runs Python. It is not a pure graph-decoration command. Unsupported creation remains refused.

## Qualification

Twelve added headless tests cover unique call target qualification, exact pin matching, parameter and literal arguments, graph/AST round trips for both operations, source-proposal immutability, Unicode/CRLF, stale anchors and external edits, direct return-call data and execution identity, preserving opaque control when effects cannot be verified, and the existing call-argument rewire path. Full suite: 468 tests passed in the packaging container. Source projection and compilation passed.

Native Qt smoke tests also validate the two new library buttons, pin actions, proposal preservation, approved reload, Call → Return projection, and capture `qualified-function-call.png`. **Only the user's Linux host qualification can close that gate.**

## Next architecture targets

Improve drag-edge feedback by querying adapter validation before a drop and make function Entry/Result ports user-editable through exact signature change proposals. Later extend qualified expression operands, nested callee resolution, and error handling with a defensible source/control IR, but do not invent connections for unsupported Python effects.
