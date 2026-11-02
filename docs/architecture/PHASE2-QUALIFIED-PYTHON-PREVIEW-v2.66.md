# v2.66: qualified graph-owned Python source preview

## State and ownership

The 2026-10-30 v2.65 WolfCat-Studio qualification report (`qualification-20261030-232026-129087.tar.gz`) passed 771 headless tests, Python-first gate and all four independently supervised native Qt stages. v2.66 is new code and **not host-qualified** until the next Linux Qt report passes.

- `program_graph.py` remains the only mutable owner of `.smi-graph` documents, incomplete states, layout, history and guarded saving.
- `python_lowering.py` is a new **read-only, Python-specific semantic qualification adapter**, not a replacement document/parser, file writer, or execution service. Its preview accepts a snapshot, returns either source plus graph-node line mapping or refusal diagnostics, and never modifies a file or executes user code.
- `gui.py` exposes the existing `ProgramWorkspace` operations through a read-only Preview Python dialog; it does not implement Python semantics itself.
- `PythonDocument` remains the source-owned `.py` parser and projection authority. No automatic bidirectional import, source publication, or cross-mode conversion is implied by this release.

## Qualified graph language (bounded v1)

All functions in a document must declare an integer return and all parameters must declare integer type. A complete function has exactly one Return, all node inputs wired, all nodes on a data path to that Return, no cycles, and no control-flow edges. Supported `operation_version=1` nodes are:

- `python.literal`: a **true integer** property `value` (not `bool`, `float`, arbitrary text or expression), output `value`.
- `python.parameter`: stable `parameter_id` reference into its enclosing function, output `value`.
- `python.add` / `python.multiply`: two required `left`/`right` inputs and a `result` output, pure integer operations.
- `python.return`: exactly one per function, required `value` input.
- `python.call`: stable `callee_id` targeting a declared function in the same graph document; ordered required arguments match that callee's current named inputs, output `result`. All graph-owned functions are qualified as the same restricted pure integer subset. Recursive call graphs are rejected.

Only `py:int` and declared `py:unknown` *port annotations* are permitted on this subset; the qualification derives integer behavior from the operation and integer function signature. Unknown operation IDs, incompatible ports, old signatures, unsupported properties/effects, or stale parameter references remain persistable but block code generation. This is deliberately not arbitrary Python, runtime type checking, or general effect-control semantics.

## Determinism and safety

- The adapter builds a Python AST rather than concatenating code fragments. Both `ast.parse` and `compile(..., 'exec')` validate the candidate; neither executes it.
- Emission uses a stable topological ordering by node IDs, one temporary binding per pure operation and call, and generated names that avoid collisions with declared parameters/function names. A shared call node is evaluated exactly once when its result fans out.
- Function ordering is canonical by name, independent of UI layout, array order and document revision. Graph node IDs map to generated source line numbers.
- A full-document issue refuses a full-document preview; unsupported/orphan operations are never silently dropped. Bound: 256 nodes per function, 200 KB generated source, additional structural limits from ProgramGraph.
- Preview only: no automatic Python file publishing, no runtime execution, no imports, no macros or loops, no user-defined side effects, and no reliance on arbitrary source strings in node properties.
- `ProgramGraph._replace` now compares exact canonical JSON content (excluding monotonic revision), not Python `dict == dict`, because `1 == True` otherwise conceals a meaningful value-type edit.

## Accepted alternatives / rejected shortcuts

1. Treat every known node label as executable and assemble Python source strings in Qt: **rejected** (duplicates semantics, unstable effects and hidden code injection).
2. Convert incomplete graph documents into Python by omitting disconnected nodes: **rejected** (silent data loss).
3. Add a separate Python lowering adapter with explicit subset and fail-closed diagnostics, while retaining ProgramGraph as owner: **implemented**.

## Verification and next gate

Run `python3 scripts/program-graph-python-gate.py` to check a committed two-function `.smi-graph` example without executing it. `python3 -m studio_native.python_lowering examples/qualified-integer-program.smi-graph` prints the read-only preview. Tests include behavioral comparison in a separate **test-only** explicit `exec`, integer-vs-Boolean edit revision, cyclic and recursive graphs, unsupported operations, stale signatures, disconnected inputs, no implicit execution, source maps and stable serialization.

Native Linux Qt must validate the Preview Python dialog and qualified authoring gestures. Only then proceed to real graph-owned source publication, function contract reconciliation, more Python types, control and effect semantics, and Blueprint-quality usability. Do not promote a second-language adapter.
