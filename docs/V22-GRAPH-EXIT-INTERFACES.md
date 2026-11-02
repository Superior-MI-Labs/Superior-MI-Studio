# Superior MI Studio v2.2 — Unified Graph Exit Interfaces

## Scope

This is an incremental refactor of the v2.1 application, not a new graph engine or visual programming language. Source files continue to own their semantics. The existing AST analysis, guarded source edits, recursive graph surfaces, filesystem graph, right-hand source editor, and compact node renderer are retained.

## One return interface, two facets

A composite **function** has one `return` exit descriptor. The descriptor is immutable and identifies:

- `kind='return'`: semantic exit category.
- `value_port`: a pre-existing typed function interface output port, or `None` if absent.
- `control_anchor_id`: stable control-completion display identity. This is **not** a new source port or executable statement.
- `sites`: exact IDs of source-backed `return` statements, including early returns in `IF` and loop regions.

The contract never creates additional source nodes, control-flow edges or data-flow edges. It validates each exit-site owner against its source metadata and rejects duplicated or fabricated claims. The Qt renderer now reads the **validated `InterfaceDescriptor`** rather than independently trusting an extra GUI dictionary.

Each expanded function displays a typed result dot on the actual composite border and an adjacent white completion marker. The old duplicate inner return dot remains an internal alias for existing boundary-edit resolution, but is **not drawn**; the outer dot is the visible target. For visible early `RETURN` statements, the rendering layer draws a non-editable normal-completion route and, if a return value exists, a value-transfer route to the same function interface. These are *visual projections of source-level exits*, not mutable program edges. The `RETURN` operation still has an execution input, optional value input, and **no ordinary execution output**.

The existing guarded edit supports dragging a qualified source value to a **single terminal return** using the visible return dot. Editing ambiguous multiple/early returns through that boundary is refused rather than guessing which statement to rewrite.

## IF and loop interfaces

An `IF` has an execution input, condition data input, and True/False execution outputs. `IF` does **not** obtain a return pin when a return statement appears in its body. The return site is linked to the enclosing function by its source-backed exit identity. For loops, Body and Completed outputs remain distinct control channels. Nested regions use the same normal graph-surface and port machinery.

The normalized contract uses a source-owned `control_port` for existing `IF`/loop execution outputs. A function return exit can expose a control completion facet without manufacturing an extra compiler-level control port.

## Cross-language principles

1. **Operations** specify source meaning and capabilities, not GUI type names. Every language adapter may emit compatible graph and interface descriptions.
2. **Regions** own child graph surfaces and expose interfaces; presentation does not impose an extra programming-language scope.
3. **Ports** represent typed data/control channels. **Exit descriptors** group nonlocal completion with optional returned values.
4. **Edges** carry real data/control/reference relations backed by the producer. Exit visualization does not add edges to the canonical source graph.
5. **View state** owns positions, selection, expansion, pan, and zoom. Changing view state must not change source files.
6. **Unknown semantics** must remain source-backed and read-only until the adapter can validate edits.

### Qualified examples

- Single terminal `return a` is folded into the function boundary.
- `if condition: return a; return b` has two source return sites converging on **one** function exit description, while both early control paths remain distinct.
- `while condition: if ...: return ...` targets the function exit, not the nearest `IF` or loop.
- Bare return carries no value input.
- Multiple return paths cannot be rewired via the single-terminal editing shortcut.
- The composite and source node/edge identity sets are unchanged when the exit contract is produced.

## Verification and limits

- **207 headless Python tests pass**, including 16 new tests for return ownership, boundary identity, `IF`/loop outputs, invalid contracts, and cross-function exit claims.
- `compileall`, Bash script checks and archive integrity are required release gates.
- The Qt smoke test has been updated to assert one visible return dot, the control facet, and nested early-return routes. This test **must run on the Linux host with PyQt6** before calling the GUI qualified. PyQt6 is not present in the artifact build environment.
- Generated exit routes are presentation-only. Their editable semantics and generalized drag-to-rewire across early/nonlocal exits require a later source-transform qualification. Exceptions, yields, asynchronous cancellation and dynamic dispatch are not newly implemented by this patch.
- Language-neutral interface descriptors now feed Qt exit rendering, but the rest of the Qt renderer still uses existing view dictionaries for layout and visual styling. Migration should be incremental, not a wholesale rewrite.
