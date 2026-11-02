# v0.5 — guarded source rewiring and dynamic-node layout

## Source of truth

`studio_native/python_graph.py` builds derived Python graph views from a real
`.py` file. `studio_native/python_edit.py` alone proposes changes to those
sources; accepted proposals use its existing guarded backup/atomic save flow.
The canvas does not store changed Python connections as a competing JSON graph.

## Limited real visual programming

Dragging from a **LITERAL** or current-function **PARAMETER** output to the A or
B input of a normal arithmetic/comparison node, or to a supported unary
operand, now asks the source-transform module to propose a Python edit.
The exact source changes are displayed in a diff dialog. Cancel leaves the
file alone. Apply creates a create-only backup and writes the new source.
Existing-source checks prevent common stale-write cases, but are not a
cross-process atomic compare-and-swap lock.

Only nodes in the same validated function scope are supported. This transforms
one operand in existing Python syntax; it does **not** create a live stored
signal, and it does not synthesize new declarations or change Python evaluation
rules. Source output expressions, closures, globals, branch outputs, variable
setters, unsupported language operations, and cross-scope rewiring remain
read-only. No Python code runs as a side effect of inspecting/rewiring.

### Visual appearance

Source nodes keep compact Blueprint-inspired shapes. The source pin/label hit
surface is reused; potential rewiring outputs now begin a preview edge.
The other end must be an existing valid source input. The inspector describes
which source edits are currently supported. White execution edges remain
read-only; only the selected operand transform can write Python.

### Dynamic node UI

The non-executable node-design sandbox now supports an optional typed local
fallback value for inputs of types: `u32`, `i32`, `f32`, `f64`, `bool`, `string`.
Double-click an input pin, or use the inspector's `Fallback: Edit` / `Clear`
control. When port labels are visible, unconnected ports show their fallback
beside the label. A connected input hides it but the fallback remains stored
in the authoring JSON and reappears if disconnected. This is prototype data,
not a new Python function-default or runtime execution mechanism.

The QWidget layout now emits resize invalidation to its existing NodeItem,
which synchronizes proxy/widget geometry and outer background. A Linux host
must run the Qt smoke regression to qualify these interactive details.

## Verification

- Headless regression: 41 tests passing in build environment (3 new fallback
  tests, 7 source rewrite tests); see `./doctor.sh` for current evidence.
- Python `compileall` / shell syntax: pass.
- Native Qt: not available in build environment, opt-in `./test-qt-offscreen.sh`
  on Linux Mint.
- Windows: launcher supplied; Windows host qualification pending.

## Remaining tasks

- Qt host smoke for drag/drop and render at multiple zoom values.
- Expand rewiring to binding reads, constructor inputs, function calls, loops,
  and branch-aware dataflow with language-specific source transformations.
- Graph history across source diffs and the text editor; explicit reparse on
  external filesystem edits; truly transaction-safe cross-process save policy.
- Interpreter/toolchain adapters, diagnostics and debugger integration.
