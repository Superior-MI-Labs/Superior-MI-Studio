# v2.15: Dock regions and navigation chrome

## Evidence and qualification

Host baseline: `qualification-20261029-020426-218365.tar.gz` on Linux Mint passed 308 headless tests and `NATIVE_QT_SMOKE_PASS`. Existing host screenshots confirm the source graph, return boundary, nested graph and breadcrumb navigation draw; they also show that dock panels occupy substantial horizontal space. v2.15's new Qt behavior cannot be qualified in the package-building environment because PyQt6 is not installed. The host must run the offscreen smoke, inspect `dock-collapsed.png`, and upload the report.

## Decision

Use Qt's existing `QMainWindow` / `QDockWidget` placement and floating controls. Avoid replacing the docking system or attaching separate ad hoc hide widgets to every editor. Introduce a single `DockRegionController` per **side region** (`left`, `right`), with each controller owning the three possible view states. Right region contains both Source Editor and Node Inspector; left contains Library. The standard Qt View menu still offers individual dock-window visibility if one is closed outright.

### Three mutually exclusive modes

- `pinned`: registered dock contents visible; restore their remembered horizontal extent.
- `collapsed`: dock widgets remain registered and their custom title/grip remains visible, while dock contents are hidden; request minimal width from Qt's native splitter layout.
- `auto-hide`: collapsed by default; hovering the title grip temporarily reveals the region. A short timer collapses it when the pointer leaves all participating dock containers.

The grip's **double-click** toggles pinned/collapsed. **Right-click** opens the mode menu. Left-button press/move/release are ignored by the grip so Qt can retain native dragging and floating. Auto-hide is not applied to floating windows; trying to enable it for a floating dock pins the region instead.

`PresentationStore` is the only state persistence authority, with a validated `dock_modes` map and backward-compatible pinned defaults. `studio_native/docking.py` owns Qt interaction and the region state machine. Neither changes source text, node metadata, graph edges, node inspector data, or filesystem resources.

### Breadcrumb actions

Each Files / Python page keeps one `QToolBar` instance and one `NavigationHistory` / `Route` authority. The bar order is `⋯  ‹  ›  ↑  [breadcrumbs / address]`. All view/context commands, including frame, mode switch and expand/collapse, are inside the left menu. Deep ancestry still uses its own breadcrumb overflow menu, so navigation actions cannot be mistaken for the view menu.

## Risks / limits

- Qt does **not** promise a high-level auto-hide dock-area API. The underlying dock splitters and resizing are managed by native Qt, but the visibility behavior needs Linux-host testing, especially when panels are moved, floated, tabified, closed, or repeatedly hovered.
- The controller deliberately does not reorganize the editor and inspector into a new custom docking framework. If more dynamic dock grouping is required, use Qt's actual area membership and the same controller, rather than creating a second pane hierarchy.
- Independent graph sessions, control-region breadcrumb targets, contract-only renderer geometry, and additional language adapters remain planned and are **not claimed** to be delivered by this release.

## Regression gates

1. Headless doctor passes 314 tests; syntax and archive integrity pass.
2. Host smoke checks each bar's left menu and contextual commands; the right region owns both right-hand docks; collapse leaves title/grip accessible; pinned restores content; auto-hide opens on hover and collapses when requested; source editor bytes stay unchanged.
3. Host screenshot `dock-collapsed.png` shows reclaimed graph space and accessible grip. The normal workspace screenshot confirms breadcrumb placement.
4. Installer must preserve previous applications and logs if native Qt qualification fails; no broad process kills or unrelated folder deletion.

## Following release priorities

1. Independently owned `GraphViewSession` per tab, with document/region/camera/selection/history identities and source authority unchanged.
2. Complete descriptor-driven renderer and distinguish execution certainty from data, call references and nonlocal exits.
3. Better horizontal graph layout and adapter-driven source relationships.
4. Qualify a second read-only language adapter after stable session and renderer contracts.
