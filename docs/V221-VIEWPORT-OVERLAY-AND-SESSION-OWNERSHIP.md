# v2.21 — Minimap viewport ownership and graph session camera routing

## Host evidence and root cause

The uploaded WolfCat-Studio qualification archive (`qualification-20261029-040047-222970.tar.gz`) reached the minimap assertion before failing with `geometry=QRect(2821,1874,228,154)` and `viewport=QRect(0,0,809,789)`. The old overlay position corresponds precisely to a viewport measuring 3061×2040; an overlay was left at the coordinates of a previously sized/hidden Qt viewport. This is a presentation lifecycle error, **not** a source-code, AST, or graph-camera bug. The recurring `propagateSizeHints()` log entries are nonfatal platform warnings.

## Implementation choices

Two approaches were considered:

1. **Patch the smoke test to call `_place_overview()` or clamp the asserted rectangle. REJECT.** This would allow the user-visible overlay to remain offscreen after tab/layout changes.
2. **Make the live viewport own the overlay geometry. ACCEPT.** Keep the existing `GraphOverview` as a viewport-child widget; install an event filter for viewport Show/Resize, reposition on graph view Show and tab activation, and schedule a settled recheck on the next Qt event-loop turn. A single `_place_overview()` handles every event; it consults one Qt-free `overview_viewport_geometry()` policy. No new overlay subsystem, source graph or camera is created.

The overlay is now resizable rather than `setFixedSize()`. On very small viewports it hides rather than painting outside its parent. When the viewport grows, it uses the existing visibility preference to reappear. The graph-camera values continue to live in the existing persisted presentation state; `GraphViewSession.camera_slot()` delegates identity construction to `root_camera_slot` and Qt reads that active identity rather than guessing a route itself.

## Regression gates

- Headless pure geometry tests reproduce the *exact* old and new rectangles, validate small-viewport bounds, and reject nonfinite dimensions.
- Session route-history tests ensure a camera slot follows the active route while two tab identities cannot collide.
- Native Qt smoke includes a deliberate offscreen placement while the source tab is hidden, switches back, and requires the overlay geometry to fit the actual viewport. This is real QWidget lifecycle evidence, not a static source-only test.
- Existing source, draft-editing, node, exit-routing, and installer suites must all stay green. The installer must preserve prior versions/logs until native Qt qualification passes.

## Qualification status

- Packaging host: **352 headless tests passed**, plus fresh extraction/ZIP and installer safety checks.
- Native PyQt6 GUI: **not qualified in the packaging environment**, where PyQt6 is unavailable. Requires `RUN-ALL.sh` on WolfCat-Studio; do not claim the Qt regression is fixed there until host evidence confirms it.

## Next engineering stages

1. Move each graph canvas's document/route, selection, camera and navigation ownership to its own `GraphViewSession` without copying source graphs or splitting source authority.
2. Introduce real closable independent tabs, then consolidate Files/System and source graphs into a universal resource-driven workspace. Preserve nested/focused as navigation views of one canonical graph model.
3. Continue generic descriptor consumption in the renderer and explicit certainty of control/effects in the language adapters. Use actual host screenshots to guide large-graph layout/edge refinements.
4. Qualify a second read-only language adapter on stable interfaces, then design guarded text↔graph round-trip edits.
