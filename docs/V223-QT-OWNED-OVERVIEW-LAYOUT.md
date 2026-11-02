# v2.23 — Qt-owned viewport layout, not manual minimap positioning

## Root-cause finding

The v2.20/v2.22 Linux smoke reports repeatedly captured the same failure:
`GraphOverview.geometry()` retained a position from a previous viewport size.
The map's parent was the live viewport, but the map's *position* was manually
managed by `GraphCanvas._place_overview()` and scattered resize/show callbacks.
The former `overview_viewport_geometry()` helper could return a correct rectangle
while the live widget displayed a stale one. Its positioning output has been
removed: `overview_viewport_size()` only produces optional maximum dimensions.
More callbacks or clamping could not solve the split ownership.

## Architectural decision

Keep the one `GraphOverview` widget, its existing camera projection and drag
logic. A `QGridLayout` on the real `QGraphicsView.viewport()` becomes the sole
owner of the overview widget's geometry. The viewport layout anchors it bottom
right with a 12px margin. `GraphCanvas._place_overview()` only controls
visibility and maximum size. It never calls `setGeometry()` or `move()`.

This is a presentation-only repair. The graph descriptor, source parser,
source editor, exit routing, and view-session camera identity are unchanged.

## Verification

- Headless regressions protect the Qt layout ownership contract and test
  live-view lifecycle coverage, but do not prove native Qt layout behavior.
- The host Qt smoke verifies actual viewport containment, forces viewport
  shrink from 3061x2040 to 809x789, and switches tabs after intentionally
  corrupting the overlay position. A second repeat on the Mint host should
  complete before declaring the release fully qualified.
- If the native layout is incompatible with this version of PyQt6, revise
  the container architecture, do not reintroduce manual coordinate writes.

## Broader roadmap

Next: move route/document/view/camera ownership into per-tab view contexts,
then unify resource/source graph tabs, continue descriptor-driven rendering,
qualify execution semantics, and introduce a second language adapter. Do not
build new tab controls over shared global mutable document state.
