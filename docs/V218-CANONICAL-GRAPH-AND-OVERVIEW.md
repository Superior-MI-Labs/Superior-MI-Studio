# v2.18: Canonical recursive graphs and camera overview

## Architectural decision

We evaluated (A) swapping between a flat focused control-flow graph and a nested whole-file graph, and (B) using one recursive source projection with different viewport roots. **Choose B.** Focus must not change the identity, ports, or semantics of `IF`, loop, return, or call operations. The Python AST/source remains authoritative. Source-backed editing remains guarded and unchanged.

An Unreal-style Branch is a control operation; a collapsed graph is a container for operations. Collapsed graphs use internal interfaces/tunnels, not a second meaning of the same source operation. Functions, calls, control regions, and scopes remain distinct contracts. Blueprint tabs and breadcrumbs change where the graph is viewed, not its meaning.

Epic reference: https://dev.epicgames.com/documentation/unreal-engine/graph-editor-for-the-blueprints-visual-scripting-editor-in-unreal-engine and https://dev.epicgames.com/documentation/en-us/unreal-engine/collapsing-graphs-in-unreal-engine

## Implementation

1. `PythonDocument.composite_file_graph(..., focus_scope=...)` now uses the already established source `presentation_graph` operations as a recursive presentation in the target scope. It does not instantiate new AST operations or change existing semantic edge identity. It retains nested control-region ownership and the inner-boundary rules.
2. `graph_routes.resolve_graph()` uses the same composite source producer for whole-file and focused routes. Focused `module` remains valid. `NativeLab` passes collapsed-region state in both cases.
3. `GraphOverview` is a small child of the existing `GraphCanvas` viewport. It uses Qt's current root camera and visible top-level node scene rectangles. `graph_surface.overview_map()` is a pure projection with no Qt, interpreter, filesystem, language, or persistence dependencies. Panning is performed through the existing `QGraphicsView.centerOn()` and `_save_root_view()` methods.
4. `⋯` exposes a checkable Overview minimap option. No new top-level toolbar or source execution path.
5. The native smoke test checks camera targeting, no scene mutation, visibility toggle, and captures `graph-overview.png`.

## Limits and follow-up

- Nested control-region **focus routes** are still explicitly unsupported; only lexical scopes are separately focusable. Do not conflate lexical scope with presentation containment.
- The map covers the **current root graph** and its visible top-level nodes. It does not navigate a child embedded camera independently. A future independent graph-view session can make any qualified region the current root, using this exact map without a separate per-language implementation.
- Very large, offscreen graphs remain readable through focus, pan, and minimap; `Fit` retains its existing readability floor.
- The application is still single-source-canvas/global-document UI, not independently owned multi-graph tabs. It remains a priority to move document/scope/camera/selection ownership into per-view contexts before adding tabs.
- True bidirectional source and visual programming requires a source-provenance-backed edit IR, deterministic transformations, diff review, parser/compiler validation, and round-trip tests. Do not derive executable source from SVG/Qt drawing geometry.
- Qt host event/rendering qualification is required before any claims of visual success. The packaging environment does not contain PyQt6.

## Tests

- Same source node/port/edge IDs in focused and whole-file projections; no changes in source bytes.
- Collapsing a region changes only visibility; source connections remain invariant.
- Overview map roundtrip, finite geometry, empty/no-op and invalid input checks.
- Qt host: visible overlay, main camera moves to map target, node/edge IDs unchanged, toggle works, screenshot captured.

## Remaining release roadmap

1. Real per-view graph context ownership; multiple independent document/function/resource tabs; Ctrl+double-click opens in another tab.
2. Remove separate Files/Python root tabs once unified resource-to-language adapter routes have a working Qt session owner.
3. Consolidate descriptor-driven rendering and edge/exit evidence, including call effects, exceptions and unverified execution.
4. Better wide layout, wire readability, dock testing, and graph search.
5. Second read-only language adapter through common contracts; only afterward begin a guarded bidirectional programming pilot.
