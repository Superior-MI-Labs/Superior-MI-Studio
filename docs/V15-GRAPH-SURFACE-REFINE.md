# v1.5 — Compact Recursive Graph Surface and Readable Layout

## Three connected priorities

1. **Compact resizable graph frames.** An expanded source composite has a 29-unit one-line header, a 31-unit child-surface offset, 6-unit horizontal inset, and no pin-reservation band. Its external semantic port handles live on the left/right borders. Each external port is mirrored as an inner **view anchor**, with the *same port ID*; it does not create a separate binding or compiler operation. All four graph corners have resize hit zones, handled by the shared canvas before an empty-space pan can swallow the drag. Frame sizes survive redraw in presentation state.
2. **Shared recursive regions.** The same GraphSurfaceItem represents the file workspace, function scopes, and now supported `for`/`while` body regions. AST-specific rules only decide which existing source nodes belong to a loop's body; Qt ownership, camera, clipping, and rendering are shared. Double-click an expanded loop node to collapse its region; double-click to restore. No artificial `LOOP BODY`, entry, or repeat operation is added. Python loop bodies **are not separate variable scopes**. Internal control/value anchors are visual; they are not an authorization to rewrite Python across scope boundaries.
3. **Deterministic compact source-aware layout.** `studio_native/graph_layout.py` contains the shared language-agnostic placement algorithm. At file level, definitions form a source-order column and module execution/call sites align alongside their dependencies. Inside graphs, nodes appear in source-line groups and same-line producers precede consumers. No source edges or IDs change. Manual user positions remain separately preserved in GUI view state. Full Sugiyama layout, incremental avoidance, and custom layout preferences are future improvements.

## Additional fixes

- `GraphSurfaceState` no longer clamps panning to the original content bounds. Users can pan into empty space even after the entire region fits on screen. `fit_contents()` is an explicit initial camera operation, not a limit on navigation.
- Expanded function parameters reuse the composite interface. Their underlying source-backed `PARAMETER` nodes and edge IDs remain available in Analysis and source editing, but the duplicated cards are hidden in Whole File presentation. The edges are anchored to their inner boundary mirror when possible.
- Composite headers display source-like signature lines such as `def countdown(value: int) -> int:` and `while value > 10:`. Full original information remains in the inspector; long labels may be visually elided.
- Window title reports Lab 1.5. No change to the authoritative Python file, parser, or reviewed-write guardrails.

## Current limitations / honesty

- **Source-aware, not optimizer-grade layout.** It handles common small programs substantially better, but complicated dependency cycles, cross-region references and hundreds of same-line expressions may still generate crossings. It does not invent a topological execution order for expression-only/control-flow graphs.
- **Loops within loops** use the same visual regions, but loop-carried values, Python `else`, exception effects, branch dominance, and side effects still have bounded analysis. Rewiring uncertain execution or environmental data stays unsupported.
- **Inner interface ports** mirror existing source-port IDs and are visual anchors, not a complete interactive graph-boundary source-edit transaction system. Direct source rewiring remains limited to qualified existing cases.
- **Root canvas** shares the scene-graph coordinate/ownership model, but window resize and zoom still use QGraphicsView; nested graph resizing is an item-level presentation interaction. Camera settings persist during this application session.
- Qt interaction, corner dragging, clipped mouse hit testing, and painting **must be qualified on Linux-host PyQt6**. The headless test suite cannot prove GUI behavior.

## Qualification

1. `./doctor.sh` for headless Python tests, source checks, and bundled examples.
2. `./test-qt-offscreen.sh` for Qt paint, file pickers, scene rebuild, nested regions, resizing, and geometry.
3. Live host: open `examples/python-v15-boundary-regions.py` as a graph; inspect `accumulate`, `countdown`, `nested`; drag each corner; pan blank space with left/middle; Shift+middle parent; Ctrl+middle root; wheel zoom; collapse/expand a `for` and a `while`; verify Python source bytes unchanged.
4. Confirm external port dots are on the composite border, inner port dots along the child viewport border, titles in one compact line, and no header overlay on the child graph.
