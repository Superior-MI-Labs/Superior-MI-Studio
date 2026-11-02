# v2.24 — Minimap geometry ownership and regression plan

## Evidence, not speculation

The Mint diagnostic on 2026-10-29, against v2.23, reproduced a minimap at (1528,1269) (228 x 154) with viewport 809 x 789, despite the viewport's `QGridLayout` reporting the correct 809 x 789 geometry. The minimap was parented to the viewport and visible. `layout.invalidate(); layout.activate()` immediately moved the same widget to (569,623), within the viewport, without modifying the camera or the graph. Other explicit layout/visibility experiments also resulted in correct placement. The failure was therefore not the graph scene projection or the viewport-size policy.

## Architectural decision

Two approaches were considered:

1. **More viewport event triggers and forced layout activation:** Small patch, but keeps application overlay content attached to the internal viewport managed by `QAbstractScrollArea`. Previous releases attempted several variations and repeated the failure.
2. **One ordinary QWidget graph-page host:** The graph view and minimap are sibling widgets in a common `QGridLayout` owned by our application. Qt owns their geometry within the page. The viewport remains exclusively the scroll area's responsibility. **Chosen** because ownership is explicit and language/canvas-neutral.

The existing `GraphOverview` still draws the same scene projection and performs the same camera navigation. No new camera store, graph renderer, source nodes, adapters, or shadow model were added.

All four existing canvases use the same `_graph_page` host when displayed. Legacy canvases are lazily hosted in their developer tabs; `current_canvas` resolves those pages to the underlying canvas, preserving the existing interaction contract.

## Testing and acceptance

Headless static tests assert there is no viewport-owned overlay layout and no manual widget positioning; they verify all graph-page paths use the one host. The native Qt smoke now tests:

- minimap parent is the normal graph host, not the graphics-view viewport;
- graph and minimap are sibling layout items;
- overlay is contained after source navigation, actual top-level window shrinking and expansion, and switching graph tabs;
- camera manipulation changes only the viewport, not source-backed graph nodes or edges.

Native Qt still needs a real Mint host result. Do not claim pass from static tests alone. Any failure should report parent, host rect, minimap rect, and layout state. No legacy versions or logs should be removed before successful host qualification.

## Next work, preserving the roadmap

After host qualification, extract genuinely independent document/route/camera/selection contexts for real multi-graph tabs. Then merge resource and source navigation, continue descriptor-driven rendering, qualify control/effect uncertainty, implement guarded visual-to-source edits, and prove a second language adapter.
