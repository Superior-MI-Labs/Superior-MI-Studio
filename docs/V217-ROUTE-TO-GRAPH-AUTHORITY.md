# v2.17: Route-to-graph authority and unified Python file opening

## Evidence and release decision

The v2.16 WolfCat-Studio host report `qualification-20261029-025628-219445.tar.gz` contains 319 passing headless tests and `NATIVE_QT_SMOKE_PASS` with eight screenshots. This is the qualified GUI baseline; v2.17 UI changes must be qualified again on that host.

Two approaches were evaluated:

1. Add new Qt tabs now and swap `NativeLab.python_doc`, `source_scope`, `source_graph`, and camera globals when the active tab changes. **Rejected**: fake independence, possible lost source-editor edits, and multiple sources of truth.
2. Resolve `Route` through the existing owner adapter, validate its graph, and deduplicate the GUI's source-opening paths before changing Qt page ownership. **Selected**: a safe incremental prerequisite to real independent tabs.

## Changes

- `graph_routes.resolve_graph()` is a Qt-free dispatcher. `resource` delegates exclusively to `resource_graph.directory_graph`, and `source` delegates exclusively to the existing `PythonDocument` presentation APIs. It returns the exact producer graph, the immutable `GraphDescriptor` validation snapshot, the canonical route, and (only for Python) the document used. There is **no extra graph registry, file cache, Python analyzer or source editor**.
- `NativeLab.browse_resource`, `navigate_source`, `reload_python_source`, and Whole File use this one boundary. File-picker and resource-double-click share `_open_python_source_path` with one unsaved-editor safeguard, layout restoration, source-editor refresh, and session binding sequence.
- Unknown file languages, unsupported nested-region focus, mismatched document identities, invalid source scopes, and resource routes with Python state fail closed; the renderer must not improvise semantics.
- Added eight unit tests for route resolution, source identity preservation, syntactic origin validation, symlink traversal safety, unsupported paths, independent sessions, and nonexecution. Native Qt smoke checks file opening through the new shared route.

## Ownership and limits

**Unchanged owners:** Python source file and `PythonDocument` own analysis; `resource_graph` owns directory snapshots; `semantic_contract` validates graph descriptors; `GraphViewSession` owns route history. The Qt scene still renders from the same existing node/edge dictionaries after validation. This is not yet complete descriptor-driven rendering.

**Not implemented here:** independent Qt graph tabs, in-place source-file expansion inside filesystem graph, nested `if`/loop region breadcrumbs, second-language adapter, visual dock or layout overhaul, fully qualified call-effect flow. These need later contracts and host tests. No region is silently mapped to a lexical scope, and no Python file is executed to build a graph.

## Next major development gates

1. Extract a `GraphViewContext` interface consumed by `GraphCanvas` without window-global source/resource fields. Keep node interactions and source-editor selection bound to the owning context. Test two simultaneously visible views with different sources and independent cameras, including unsaved-editor guards.
2. Implement closable multi-graph tabs using that context. Double-click expands inline; Ctrl+double-click opens the same resource/scope in a separate tab; breadcrumb history is per-tab. Refuse unqualified region focus.
3. Retire the separate Files and Python root workspaces only after the single resource-rooted view can descend into `.py` views without duplicate source models. Continue descriptor/flow consolidation and language adapters.

## Qualification status

The package passes headless tests and ZIP/source-integrity gates. PyQt6 is unavailable in the artifact container; the new Qt smoke assertions must be run on WolfCat-Studio before marking v2.17 native GUI qualified. The installer preserves prior versions and logs until those host checks pass.
