# v2.16: Per-view route authority and universal-workspace direction

## Evidence

The v2.15 Linux Mint host qualification report `qualification-20261029-023837-219092.tar.gz` passes the headless suite (314 tests) and `NATIVE_QT_SMOKE_PASS`. Its screenshots confirm the focused control-flow graph is more legible for large code sections, while inline expansion preserves parent context. Neither is a different programming language or compiler graph. The dock-collapsed screenshot verifies the Qt region grips remain visible, although manual host review is still needed to evaluate hover UX and reclaimed space during ordinary use.

## Architecture decision

Retain both **inline expansion** and **focused presentation** as two *view states* backed by the same source contract. Do not attempt to choose one permanent representation for all graph sizes. Normal double-click expands/collapses in place. The target Ctrl+double-click gesture opens the same resource/region in a distinct graph-view tab; a tab owns history, camera, selection and view preferences. The original source file or resource provider remains the single authority. Files are resource nodes; language adapters can provide a graph projection when qualified. No provider may auto-execute code on file expansion.

Build on the existing `Route` and `NavigationHistory` rather than inventing a second navigation model. `GraphViewSession` is one tab's route and history owner. `GraphViewSessions` owns tab membership. Existing Files/System and Python tabs now consume this one contract. The current Qt UI **does not** yet implement arbitrary session tabs, and file/source state remains global until the UI adapter is migrated. Do not pretend the pure session registry alone solves that dependency.

## Why not collapse into one canvas immediately?

The current `GraphCanvas` and node interactions use `NativeLab.python_doc`, `source_graph`, `source_scope`, `resource_graph` and the editor binding. Reparenting that canvas and calling it a unified workspace would let two tabs silently share their source, camera, or active node. The session contract must be integrated into the data and scene ownership first. Avoid temporary mirrors, global-state swapping, or one-off Qt page forks.

## Follow-on gates

1. Per-session graph producer/adapter resolution: resource directory, source file, lexical scope and nested control regions; use validated descriptors and keep unsupported resources read-only.
2. Move `GraphCanvas` and editor selection to the active `GraphViewSession`, then enable real `QTabWidget` add/close/new-tab behavior. Preserve independent cameras and undo/history.
3. Make the normal workspace a resource-rooted tab, with `.py` double-click expanding the source graph in place and Ctrl+double-click opening a separate tab. Leave legacy tabs reachable through View > Legacy / Dev during the migration.
4. Generalize source adapter contract and separate proven control from effect uncertainty before qualifying a second language.

## Verification

`./doctor.sh`, shell syntax and ZIP integrity are package gates. Native PyQt6 smoke must run on Linux Mint; no GUI qualification is asserted from the container. The existing tests for return terminals, recursive regions, graph descriptions, and source edits must remain green. Additional headless tests cover independent histories, cross-kind route transitions, tab close/replace behavior, invalid destinations and unchanged source IDs.
