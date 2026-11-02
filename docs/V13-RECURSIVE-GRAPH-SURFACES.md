# v1.3 — Recursive Graph Surface Refactor

## Architectural owner and shared primitives

This changes **Qt presentation and input handling**, not the Python graph authority. The source file and PythonDocument AST-derived IDs remain the only source of truth for code. No new programming operations are created for viewport control.

- `GraphSurfaceState` (`studio_native/graph_surface.py`): Qt-independent camera and logical content extent, bounded pan/zoom and stable cursor-position zoom.
- `GraphSurfaceItem` (`gui.py`): shared visual surface for root and nested graph workspaces, including viewport clipping, local coordinate system and independent camera.
- `GraphContentItem` (`gui.py`): sole child coordinate root for each surface; nodes and their same-graph edges are parented there.
- `NodeItem`: a normal source operation or a composite with an optional child `GraphSurfaceItem`; no duplicated semantic node.
- `PortItem` and `QGraphicsPathItem`: existing ports and derived edges are unchanged in meaning; lines are parented to their common content layer where possible.

**One Qt scene and one GraphCanvas**, not N nested QGraphicsViews. The file-level root has the same GraphSurfaceItem abstraction, while the containing main QGraphicsView provides its window-sized camera. Nested surfaces use `GraphSurfaceState` independently.

## Interaction

- The root graph scrolls/zooms/pans using existing GraphCanvas behavior.
- Each expanded composite has an independently clipped child viewport with a subtle internal grid and **no redundant header**.
- Drag **empty child graph space** with the left mouse button to pan that region; drag a child node to move only the child. Middle-drag also pans the graph under the pointer. Wheel over the child area zooms the child, not the file.
- Drag the **composite header** to move the complete node/child graph within its parent.
- Collapsing and expanding preserves each graph camera in window presentation state, keyed by the source file path and graph-scope ID. Parent graph movement does not change child graph coordinates.
- Child nodes never reparent when dragged. Negative graph-local node positions are clamped to zero; positive positions expand their logical scrollable extent, while visible content is clipped to the child viewport.
- Only the source nodes and edges are authoritative. A camera pan, resize, zoom, or node move does **not** edit Python.
- Default whole-file expansion shows top-level function/class bodies, while more deeply nested scopes start collapsed to conserve space. `Expand All` remains available.

## Geometry and readability

- Compact composite body viewport limited to **650 × 245 scene units**, at most, with independent navigation when content is larger.
- Padding and gaps inside nested regions were reduced to 12, 20 horizontal, and 18 vertical units.
- Function signature, source details, and rich metadata remain in the inspector; no new visual boilerplate is added.
- Scope ownership derives from the existing `containing_scope`/`source_scope` projection fields; no extra program graph registry or parser path.

## Explicit limits

- This does **not** yet make `if`, loop or exception-body nodes independently expandable subgraphs; the reusable surface infrastructure is ready, but those constructs need language-aware region ownership and correct boundary/control semantics.
- Cross-boundary references/edges remain derived from the existing source graph. A dedicated visual boundary-anchor routing pass is future work. They must not be mistaken for editable cross-scope flow until a safe transformation exists.
- Root camera remains delegated to QGraphicsView instead of duplicating scene navigation state in the root surface. Internal regions have independently persisted cameras.
- Qt native host rendering, mouse interaction, composite hit-testing and Windows behavior remain **unqualified in this container** because PyQt6 is absent. The host-only smoke test extends prior coverage but must be run on the user's Linux machine.

## Regression

Run `./doctor.sh` (Python/unit) then `./test-qt-offscreen.sh` (native Linux host). Pure tests check camera clamping, zoom anchoring, independence, scope geometry, stable node/edge identities and unchanged source. Qt smoke checks scene ownership, clipping flags, camera persistence across rebuild, and dragging without reparenting. Test visually by opening `examples/python-v13-nested-surfaces.py`, expanding `outer`, `middle`, `inner`, scrolling within `middle`, and dragging the whole `outer` node from its header.

Before merging into the production Studio application, repeat the tests there and verify Qt on Linux and Windows. Do not replace its canonical semantics or session owner with this standalone prototype.
