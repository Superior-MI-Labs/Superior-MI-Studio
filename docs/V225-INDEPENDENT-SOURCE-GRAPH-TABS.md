# v2.25 — Independent Python Graph Tabs (First Operational Stage)

## Host baseline

The v2.24 WolfCat-Studio report `qualification-20261029-045842-224392.tar.gz` contains `NATIVE_QT_SMOKE_PASS`, 363 passing headless tests, and nine useful screenshots. In particular, the graph overview is now inside its application-owned host, and its actual resize/tab path passed. Do not regress that layout into a managed `QGraphicsView.viewport()` overlay.

## Architecture decision: share source authority, isolate views

Options considered:

1. **Tab labels switching one global graph/camera:** rejected. This gives the appearance of multiple tabs while silently sharing selection, route, camera, and graph state.
2. **Clone the Python parser/source representation per tab:** rejected. This introduces multiple interpretations of one file and risks stale edited documents.
3. **One graph canvas and navigation session per source tab, reusing the existing route resolver and document identity:** selected. A tab holds only presentation state and a derived graph projection. The existing `.py` file remains authoritative. The window's original Python fields are temporarily bound to the active tab for compatibility with existing inspector and editing flows; they are not independent persisted sources.

`SourceTabView` is a Qt-only view container; `GraphViewSession` remains the navigation/history/camera identity authority. `GraphCanvas` has a session ID used for root and nested graph cameras. The shared presentation store remains the one owner of camera values, layout and node positions. The existing `resolve_graph` remains the only route-to-graph adapter boundary. This is an incremental migration, not a second source graph model.

## User-facing behavior

- Ctrl+double-click a Python function/scope node opens that scope in a **new independent graph tab**.
- The Graph menu also provides “Open current source in new tab”.
- Ctrl+double-click a `.py` file in Files/System opens a new source graph tab; normal double-click reuses the current Python tab.
- New source tabs have an actual close control, and Ctrl+W closes the active extra graph tab. The original Files/System and initial Python tab remain retained until resource/source tabs are unified.
- Each new tab owns its own graph canvas, focus/whole-file route, history, minimap, source-detail presentation, expansion state and selected source node. Root and nested-region camera identities are session-qualified. Editing text remains in the existing single document editor, which follows the active tab.
- Source reload synchronizes derived graph projections of *other tabs of the same file*. Those tabs keep their own view identity; disappearing focused scopes fall back to the file's module view. Editing still uses guarded source modification and reviewed diff; there is no new visual-to-source editing path.
- If the source editor contains unsaved text, tab switching/opening uses the existing discard confirmation. No implicit source writes or code execution.

## What is not claimed

This is the initial operational **Python multi-tab** stage, not the fully unified resource workspace. Directory tabs and nested control-region focus routes are not yet qualified. Global source fields are active-view compatibility bindings and are not yet eliminated from the 3,600+ line Qt shell. Inactive views retain a disposable rendered graph; their actual program meaning remains sourced from the document and descriptor.

The 368 headless tests cover identity and route-isolation invariants. The expanded native Qt smoke covers two real source tabs with the same `PythonDocument`, independent camera keys, tab switching, closing, and refusal of invalid scope routes. Until this smoke passes on Linux Mint, the GUI behavior is **unqualified**, regardless of headless results.

## Follow-on migration

1. Qualify v2.25 native Qt on WolfCat-Studio, inspect `independent-graph-tabs.png`, and fix actual results rather than guessing.
2. Pull active-view compatibility fields from `NativeLab` into the view context/adapter boundary and route inspector/editor calls to an explicit active session. No duplicate graph definitions.
3. Generalize tab ownership to resource roots and remove the permanent Files/System vs Python division. Keep double-click inline expansion; Ctrl+double-click opens a new tab. Build breadcrumbs from authoritative resource/scope relationships.
4. Continue descriptor-led rendering and language-confirmed control/effect channels. Preserve source-boundary edit validation and establish round-trip node/source transforms before enabling arbitrary visual wiring.
5. Qualify a second read-only language adapter with no language-specific Qt subclasses.
