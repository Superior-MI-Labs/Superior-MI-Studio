# v2.45 — Blueprint graph mouse gestures

## Baseline and evidence

The v2.44 user-host qualification `qualification-20261030-154601-28477.tar.gz` contains `551 tests ... OK`, `PYTHON_FIRST_GATE_PASS`, and `NATIVE_QT_SMOKE_PASS`, without Python tracebacks. PyQt6 is not installed in the patch-authoring environment; the newly changed native Qt events require WolfCat-Studio qualification. This report does not claim v2.45 native qualification.

Epic reference (retrieved October 30, 2026):

- https://dev.epicgames.com/documentation/unreal-engine/graph-editor-for-the-blueprints-visual-scripting-editor-in-unreal-engine
- https://dev.epicgames.com/documentation/unreal-engine/blueprint-editor-cheat-sheet-in-unreal-engine
- https://dev.epicgames.com/documentation/unreal-engine/placing-nodes-in-unreal-engine

These document right-drag panning, left-drag marquee selection, shift add/ctrl toggle, right-click graph actions and pin-drag compatible creation.

## Architecture decisions

**Rejected:** a second Qt scene/event framework, a manual selected-graph registry, changing node contracts to simulate mouse gestures, and allowing UI menus to manufacture unsupported Python edits.

**Implemented:** the existing `GraphCanvas` view handles right-click vs right-drag by a movement threshold; it delegates camera panning to `_pan_drag` and region ownership to `navigation_surface` (the same path used by middle-pan). The ordinary left blank-space drag uses existing graph-local `QGraphicsRectItem`, now with normal replace, Shift add and Ctrl toggle semantics. The pure `graph_surface.marquee_selection()` function determines membership independently of Qt. Right-click context requests remain owned by existing Qt node context menus and adapter-qualified `open_creation_menu`. A direct dispatch on button release avoids platform differences between context event on right press vs right release; following native mouse context events are suppressed for the same gesture. Middle-pan remains for compatibility.

The program graph, semantic contracts, source mutations, scene layout and camera persistence were not changed. Display selection never writes code. Selection clips hits to immediate nodes of the graph surface that received the gesture.

## Tests and remaining gates

- Headless tests cover replace/add/toggle, blank click, invalid selection mode.
- Native Qt smoke now exercises blank click deselection, right-drag panning, and exactly one right-click menu dispatch with event interception (no modal creation during the test).
- Actual host `RUN-ALL.sh` is required to qualify right/middle pan against the Qt backend, tab switching, source menus, nested scenes and external input devices.
- Deferred work: drag-from-pin discovery over wider qualified Python operation set; My Blueprint-style function/variable browser built from Python AST scopes; graph-level cut/copy, reroute points, comment annotations; native user-experience review including modifier keys and focus traversal.
