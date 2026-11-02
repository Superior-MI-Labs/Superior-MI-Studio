# v0.6 — Host fixes and Python source editing

## Root cause and repairs

1. v0.5 host smoke: old `NodeItem` wrapper retained across `GraphCanvas.rebuild`
   after `create_node` calls `graph_scene.clear()`. Qt deletes the old proxy,
   panel and layout. Reusing the old wrapper produced the posted
   `QVBoxLayout has been deleted` exception. Reacquire from `items_by_id`
   after any scene rebuild. Do not cache Qt scene children across a rebuild.
2. Native file chooser on Linux may depend on a broken XDG portal. Open/Open
   Python/Save As now create `QFileDialog` with `DontUseNativeDialog`, owned
   by the main window. Saving does not mutate the active path on failure.
3. New headless tests cover safely rewriting simple call arguments and
   straight-line local reads; unsupported control dependencies refuse.

## Tests run in build environment

- `./doctor.sh`: PASS, 48 tests, source-projection verification.
- `python3 -m py_compile studio_native/*.py`: PASS.
- `bash -n *.sh`: PASS.
- Native Qt GUI: UNVERIFIED here (PyQt6 not installed).

## Host test plan

Run `./test-qt-offscreen.sh` on the actual Linux Qt host. This test verifies
an actual non-native dialog appears, File menu callbacks, a scene-rebuild-
safe container resize, and existing graph navigation.
Run `./launch-linux.sh` and manually test all three File menu pickers.

## Known limits

- No general SSA/dominance analysis. Local-source rewiring only supports a
  single earlier straight-line named assignment with no unverified effect or
  rebinding between it and a simple target statement.
- Calls only expose positional operands; `*args`, keyword rewiring, and
  nested/side-effecting source operations are explicitly deferred.
- Source changes still require reviewed diffs and backups; running code is
  explicit and uses ordinary host permissions.
- Future: comprehensive dominance/control-flow regions, keyword argument
  projection, expression-level getter reads, undoable multi-file refactoring,
  and full Qt interaction verification.
