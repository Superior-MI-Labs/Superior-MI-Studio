# v2.6 Return Boundary Recovery (from user-uploaded v2.5)

## Source and limits

This release is rebuilt from the supplied `Superior-MI-Python-Visual-Programming-Lab-v2.5(1).zip`. The original interrupted agent's unshipped v2.6 files were not accessible, so this is an independently implemented recovery candidate, not an assertion of exact byte-for-byte restoration. The Qt GUI was not executed in the packaging environment because PyQt6 was unavailable. No source files are executed while visualizing them.

## Architecture decision

Compared approaches:

1. **Paint a second decorative overlay in the parent scene.** Rejected. A wire behind an opaque composite would remain invisible or require increasing it above unrelated cards; it also introduces a duplicate visual representation not attached to the source edge's identity.
2. **Resolve preexisting RETURN edges through the validated graph contract, then draw inside the owning function's GraphContentItem.** Implemented. Return sites still belong to the Python AST, and graph ports/edges keep their original IDs. The renderer consumes `FoldedExitConnection` for display geometry only.

`semantic_contract.py` now carries the source-declared `terminal_boundary_owner` as read-only `folded_exit_owner`. Hidden conditional nodes are not blindly treated as terminal folded returns. The normalized contract validates owner and return-site consistency.

`exit_routes.py` retains `project_exit_routes()` as the one source of exit metadata and adds `project_folded_exit_connections()` to bind **actual** inbound edges to their value/control facets. There is no invented control edge when the source offers none, and an inline literal return does not invent a data edge.

`gui.py` converts the preexisting source edge to a path between its actual source port and the same composite function's typed result dot or completion marker. The path is a child of the function's GraphContentItem rather than an item in the root scene behind the function. Visible early RETURN facets also target the owning function graph. `edge_presentation.py` remains the sole style policy for regular and exit-specific relations.

## Verification

- Baseline v2.5: 246 headless Python tests passed before modifications.
- New v2.6: 9 additional tests in `tests/test_v26_folded_exit_connections.py`; total 255 pass.
- `./doctor.sh`, Python `compileall`, shell syntax, and archive-integrity checks are required before distribution.
- `studio_native/qt_smoke.py` now checks actual folded data/control QGraphicsPathItem endpoints, ownership by the child function graph, node movement, camera pan, and visible early-return endpoints. **These assertions are pending execution on a Linux host with PyQt6.**
- For a manual visual check, open `examples/python-v18-boundary-and-layout.py`, expand `nested_expression`, confirm `total` connects to the return-data dot and the completion triangle (only if an existing flow edge is present), then inspect `early_exit`. Move/resize and pan the node graph and confirm the wires stay attached.

## Known limits and next decision

- The original interrupted agent also mentioned stable layout anchors across harmless source text shifts. Those changes are **deferred** because they require an independently validated identity-migration contract, not another ad hoc source-position fallback.
- A child graph clips paths to its viewport. The typed return dot lies on the surrounding function frame, where its hit circle overlaps the inner graph edge. Real-host rendering must confirm this overlap is visually seamless; if not, correct boundary geometry at its shared layout origin, not by adding separate fake wires.
- Advanced wire obstacle avoidance, dynamic control-flow rewiring, source-backed exceptional/async/yield exits, and cross-language execution remain out of scope.
- Do not merge this independent research application wholesale into Superior MI Studio production. Only promote qualified contracts after evidence and architecture review.
