# v2.27: Unified tab-context lookup and resource/source graph actions

## Qualification baseline

The v2.26 WolfCat-Studio host report `qualification-20261029-053517-226226.tar.gz` recorded **371 passing headless tests** and `NATIVE_QT_SMOKE_PASS`. It supplied ten Qt screenshots, including independent graph tabs. The v2.27 application has not yet been natively qualified on WolfCat-Studio; new host assertions are in `studio_native/qt_smoke.py`.

## Architecture audit and two approaches

**Option A: Introduce a second universal Qt tab manager and duplicate the source/resource view lifecycles. Rejected.** That would duplicate the existing `GraphViewSessions`, `Route`, `resolve_graph`, and presentation store, creating a second state authority and risking the return of stale camera/route bugs.

**Option B: Consolidate the existing Qt view contract and selected-tab lookup, keep provider-specific preferences in the existing views, and make route dispatch share their public entrypoints. Chosen.** The base `GraphTabView` contains only `session_id`, Qt `page`/`canvas`, and toolbar. `SourceTabView` and `ResourceTabView` continue to supply the same provider-specific view preferences, without duplicating a Python document or resource provider.

## Changes

1. `NativeLab._graph_tab_for_page()` is the single selected-page-to-view lookup over the existing registries. `_workspace_tab_changed()` uses this lookup; no separate registry is introduced.
2. `current_canvas()` follows the **selected** Qt page for both source and resource views, including additional tabs of the same source. The prior special case checked the last active `self.source_page` and could miss secondary Python views. The original prototype canvases remain accessible in View > Legacy / Dev.
3. Frame and Reset Zoom use `current_canvas()` rather than a fixed original source canvas. The breadcrumb menu also exposes **Open this location in a new tab** and routes it through the existing source/resource creation paths.
4. Ctrl+clicking a breadcrumb opens it in a separate graph tab; plain click navigates the existing provider view. Source breadcrumbs can now load a different supported `.py` file through the established guarded file-opening transaction, rather than refusing it as unloaded. Unsupported routes remain refused; no Python source is executed by navigation.
5. The v2.27 headless suite now includes five tests for shared Qt view inheritance, selected-canvas resolution, generic frame/zoom, breadcrumb dispatch, and cross-provider session isolation. Existing old-minimap static verification was updated to assert the retained legacy-canvas behavior via the new selected-tab lookup, not literal obsolete code text.
6. Native smoke assertions cover the canvas and framing of an **additional** Python tab, the primary and additional resource tabs, and breadcrumb new-tab creation/refusal without ghost tabs.

## Limits and follow-on plan

The selected view's `Route` and camera are session-owned, but `NativeLab` still exposes temporary `python_doc`, `source_graph`, `source_scope`, `resource_path`, and canvas aliases for legacy rendering paths. This release does **not** claim full arbitrary cross-kind transitions within one physical tab; the dedicated Files/System and Python root tabs still exist. Do not convert those aliases into a second persisted source authority.

Next: make `GraphCanvas` and node interactions resolve their active source/resource projection and editor identity from the owning view, not the window's currently active provider aliases. That unlocks switching the **same tab** between directory and source views using one `GraphViewSession` history. After native qualification, retire the permanent split root tabs and finish adapter/descriptor unification. Continue precise Python execution/effect contracts, round-trip source edits with reviewed diffs, and then a read-only second language adapter.

## Release gates

- `./doctor.sh`: source compilation and headless regressions.
- `./test-qt-offscreen.sh`: real Qt graph tab switching, selected-canvas commands, breadcrumbs, and minimap host tests on Linux.
- Exact versioned ZIP extraction and doctor rerun.
- Isolated-home Linux installer rehearsal, headless mode only; no destructive cleanup on incomplete qualification.

Do not describe host Qt as passed for v2.27 until the actual host report returns.
