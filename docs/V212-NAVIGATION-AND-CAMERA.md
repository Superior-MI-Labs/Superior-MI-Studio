# v2.12 — Navigation, readable embedded cameras, and graph workspace ownership

## Verified evidence / original priorities

- Linux Mint host report `qualification-20261029-003038-214769.tar.gz`: native Qt smoke PASS and doctor PASS for v2.11; screenshots of source return boundaries, nested boundaries, early exits and draft edits were supplied.
- Existing source/draft validation, source-backed Python editing, and return semantics were deliberately retained. Do **not** infer compiler or execution correctness from screenshots.
- User reports that a large `arrange` function shrinks to unreadable tiny nodes; pressing `Fit Graph` zooms out massively and then scrolling seems broken. The previous `fit_source_graph` called `graph_scene.itemsBoundingRect()`: this contains a `GraphSurfaceItem` spanning the fixed 8500×6000 scene rectangle, not only programming nodes. `fitInView` stored scales far below the Qt wheel's 0.25 lower boundary, so subsequent wheel events were refused. This is a view/camera defect, not a semantic defect.

## Two design approaches compared

**A. Duplicate GraphCanvas for each focused function immediately.** This is wrong while `NativeLab` has one `python_doc`, `source_graph`, `source_scope` and `source_view_mode` as global mutable state. Additional Qt tabs would overwrite each other's model/selection and create a second apparent authority. Reject as a quick patch.

**B. First correct the shared camera/navigation policy and place controls within owned tab pages, then migrate view state into per-tab sessions.** Chosen. No new semantic graph format, no duplicate AST/source analyzers and no parallel editing routes.

## Changes

1. The two regular graph pages own a toolbar and QGraphicsView in a QVBoxLayout; no QMainWindow graph toolbars. `QTabWidget.currentWidget()` maps back to the authoritative canvas when needed. Resource-specific Browse/Up/Refresh/Pagination controls remain with Files. Python-specific Overview/Focus selected/Parent/Frame/Display remain with Python.
2. Old Node Workspace and Studio Settings Graph are developer views toggled through View → Legacy / Dev, not deleted or duplicated.
3. `frame_visible_bounds()` is a Qt-free graph-surface function computing a deterministic center, bounded zoom and whether all visible content fits. The Qt canvas passes only visible *root-level NodeItems*, never scene background or nested content with a different camera. The root wheel and restored cameras now share compatible zoom limits.
4. GraphSurfaceState keeps its original true `fit_contents()` behavior for callers/tests but optionally accepts `min_readable_zoom`. New nested viewports use this option to show the first visible portion at a readable scale rather than reducing to 1%. Manual pan/zoom persists, and right-click offers an explicit reset.
5. Graph source-node mouse presses refresh the source selection even for the same already selected item, when the source is clean and the exact source span is known. Unsaved/stale source remains guarded.
6. Qt smoke checks two normal tabs, the legacy toggle, per-tab toolbar ownership, bounded framing, focused view and source caret restoration; produces `workspace-navigation.png`.

## Verification

- 297/297 headless tests PASS, including v2.12 camera boundary cases and all previous graph/semantic/draft/authoring regressions.
- Python compileall PASS; shell syntax checks PASS; ZIP archive and fresh extracted doctor to be verified before delivery.
- **Qt smoke not executable in packaging environment (PyQt6 absent). Host run required before UI qualification.**

## Next coherent releases; do not let UI ideas derail core roadmap

1. Finish descriptor-driven rendering and verify source/draft/OS graph projections don't branch into language-specific Qt handlers. Add explicit diagnostics on wrong model vs view authority.
2. Strengthen Python execution certainty and nonlocal exit representation: callable definition ≠ invocation ≠ result, proven control vs data/reference/effect. Do not invent white wires for uncertain Python effects.
3. Move single `NativeLab` source view state into an independent `GraphViewSession` with one source document identity, own scope/mode/camera/selection, and shared language adapter. Only then enable arbitrary tabs, close/reopen, and multiple focus tabs of one file.
4. Add dock-area-level collapse/auto-hide via native QMainWindow dock layout, maintaining one dock-state owner. Evaluate `QMainWindow.saveState()/restoreState()` but only for locally saved trusted state.
5. Improve horizontal organization through alternate *presentation* layout heuristics with regression screenshots, not new semantic nodes. Then introduce read-only second-language adapter through the existing normalized graph contract.

For more on native controls, consult official Qt 6 QTabWidget, QGraphicsView and QMainWindow documentation.
