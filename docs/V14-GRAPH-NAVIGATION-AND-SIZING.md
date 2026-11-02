# v1.4 Graph surfaces: controls and constraints

- One `GraphCanvas` routes navigation gestures to the deepest visible `GraphSurfaceItem`, its parent, or the root. No per-language or per-node gesture shims.
- The same `GraphSurfaceState` validates zoom, pan extents, viewport dimensions and initial fit independently of Qt.
- Function/composite sizes and cameras are **presentation state**, scoped by the source path and semantic scope key; source bytes and graph node IDs are unchanged by resize.
- Initial layout still uses deterministic source-ordered rows/columns with compact padding. It is NOT a sophisticated compiler/dependency-aware auto-layout, and large graphs may start visually small to show all content.
- Empty-space left-drag pans the owning graph at every depth. Shift+left-drag creates a selection rectangle scoped to that same graph, preserving multi-node selection. A node left-drag moves the node; an output-port left-drag connects pins. The grip resizes the composite's visible child graph. It does not reparent child nodes, alter source code, or introduce a synthetic programming operation.
- `Ctrl+Middle`: root. `Shift+Middle`: immediate parent. `Middle`: current graph. Wheel: current graph. Root zoom continues through QGraphicsView.
- All QPainter strokes using a floating composite width use point-based overloads to avoid PyQt6 C++ dispatch errors.
- Native Qt test runs only on an actual PyQt6 host. `doctor.sh` tests the Qt-free camera contract, source identities and source editing without assuming Qt UI qualification.

**Next:** Dependency-aware auto arrangement that respects manually placed positions and uses fewer wire crossings; persistent workspace save/load of camera and size; graph-region boundaries for loops and conditionals. These are not claimed to be implemented.
