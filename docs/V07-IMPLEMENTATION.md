# v0.7 — Conditional-arm rewiring, statement inputs and loop preview

Source baseline: v0.6, extended in place. No second renderer, no new graph document schema, no embedded browser.

## Implemented

1. `python_edit._straight_line_regions` divides functions into one function-body region and separate `if`/`elif`/`else` arms. A direct, named local assignment may be used as a source only when the exact target expression lives **later in that same region**, with no intervening unverified effect, rebinding, or control construct. Cross-arm/post-branch/loop transfers are still refused. Explicit `global` and `nonlocal` writes are refused.
2. `rewire_source_operand` additionally handles existing value inputs of a simple named assignment (`SET`) or `return` statement. It compiles the candidate Python AST for validity, displays an exact diff through the existing Qt dialog, then uses the existing backup and guarded save path only on approval. This is a source transformation, not a live dataflow channel or runtime instrumentation.
3. `python_graph._body_graph` projects `for`/`async for` and `while` as compact loop nodes with typed data/condition inputs, white body/exit control *handles*, and an explicitly source-backed body. Only the body entry has a control edge; **there is no invented loop-back, break/continue, loop-else, or successor edge**. Repeated `while` conditions use a source-backed repeated-test node rather than falsely linking an initial binding as if it were stable across iterations. Loop-assigned names are marked UNCERTAIN in downstream value projections; no old assignment is falsely asserted as their definitive result.
4. The native Qt renderer displays loops as compact source nodes using the same `NodeItem` and `PortItem` as all other source constructs. The inspector explains current editable targets and refuses uncertain rewires.

## Deliberate limitations

- This is not a full control-flow or dominance IR. Source-backed loop nodes are **visual structure only**. Ports labeled `exit` indicate an eventual semantic boundary, not a qualified CFG edge or executable behavior.
- A source assignment inside a conditional arm is proven available only later in that exact arm, not outside it—even if both branches assign the same name. The strict fallback is refusal.
- Calls, mutations, imports, aliases, generators, async and exception paths require effect/lifetime analysis before more elaborate rewiring.
- General graph-to-source rewrite, multiple source files, function-signature edits, debugging, and compilation are not qualified here. Ordinary Python explicit run remains available from the existing UI.
- Parsing code never imports or executes the inspected file. Running a Python file is an explicit user action under host permissions.
- Backup + stale-file detection guard normal edits; not a cross-process compare-and-swap guarantee.

## Evidence and host qualification

- `./doctor.sh` tests parser output, source edit positive and adversarial cases, existing graph/model/asset contracts. The new tests are in `tests/test_python_v07.py`.
- `./test-qt-offscreen.sh` is a **host-only** Qt GUI smoke test; it is not run automatically by `doctor.sh` and its completion must be observed on the Linux host.
- Native Qt was not available in the build container, so a successful Linux GUI run is not claimed.

## Suggested next milestones

1. Qualified loop CFG with break/continue/loop-else and reachable exit paths, plus loop-carried SSA / value joins.
2. Precise effects, aliases and calls: a reusable dominance/value proof for more source rewiring.
3. Test interaction and lifecycle on actual Linux Mint desktop, including embedded widget resizing and QFileDialog fallback.
4. A source/graph edit transaction API with undo/redo and conflict-safe saves; then additional language adapters.
