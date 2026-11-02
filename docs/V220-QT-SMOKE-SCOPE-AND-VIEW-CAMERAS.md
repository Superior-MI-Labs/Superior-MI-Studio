# v2.20 — Native Qt smoke scoping and view-specific camera keys

## Evidence and diagnosis

User's WolfCat-Studio v2.19 host run failed in `studio_native.qt_smoke.main()` at `assert model.validate(w.state)==[]` with `UnboundLocalError: cannot access local variable 'model' where it is not associated with a value`. `qt_smoke.py` imported `model` at module scope but later assigned `model=overview.projection()` in `main`. Under Python's function-wide lexical scoping, **that assignment shadows the import throughout `main`**. The application was not shown to be broken by this traceback; the Qt smoke itself aborted.

The new static test, based on Python's `symtable`, detected **two further latent collisions**: local imports of `Qt` and `QPointF` inside `main` also shadowed module-level imports. A previous v2.19 import preflight verified import *existence*, but did not detect imported symbol rebinding. Compilation does not report `UnboundLocalError` until the code executes.

## Changes

- Retain module-scoped `model`, `Qt`, `QPointF`, `Route`, and `resolve_graph` imports. Remove redundant local Qt imports from `main` and rename the unrelated minimap projection variable to `overview_projection`.
- Add a headless Python `symtable` regression that compares module imports against function-local declarations. Exercise it with synthetic shadowing examples, including alias imports. This is **test-harness coverage**, not another production subsystem.
- Create stable camera slots using the **existing** persisted `_graph_cameras` store, keyed by tab/session ID + route kind + source scope + view mode + optional region (and resource/source path). Whole-file, focused-scope and second-tab views cannot accidentally reuse the same root camera key. No separate camera state store or graph model is introduced.
- When changing focused-source routes, restore the destination's saved root camera if it exists, otherwise frame its visible nodes. Rebuilding the same route can preserve existing camera semantics. The old `@root-view` storage is a read-only migration fallback for whole-file and directory views, avoiding loss of old layout preferences.
- Add host-only Qt assertions that a function focus and whole-file view use different root camera slots and focusing cannot overwrite the previously saved whole-file camera.

## Architectural decisions

1. **Do not create new graphical tabs yet.** The Qt window still has the legacy global Python document/scope/canvas state. Multiplying canvases without transferring those state owners would create cosmetic tabs with incorrect cross-file state.
2. **Preserve source/provider authority.** No changes to Python AST analysis, graph descriptor meaning, execution-flow inference, source editing, or filesystem provider.
3. **Reuse the presentation persistence authority.** `root_camera_slot(session_id, route)` produces a deterministic *key* only; `_graph_cameras` still owns the values, and `presentation_state.py` still persists them.
4. **Test the failure class.** An AST import-existence test alone cannot find Python lexical scope errors; `symtable` can catch imports shadowed by local bindings without PyQt6.

## Qualification

- Headless `./doctor.sh`: **348 tests passing** (343 before, 5 new).
- Source compile, shell checks, ZIP CRC, fresh extraction and headless installer rehearsal required for release.
- Host-only `./RUN-ALL.sh` remains required to claim native Qt correctness. PyQt6 is not installed in the packaging environment; attempts to install it there were blocked by unavailable package-network access.
- On any host qualification failure, preserve old installed versions and logs. The installer must not prune until native Qt tests succeed.

## Roadmap, unchanged

1. Transfer source document, graph view mode, camera, selected nodes and history into truly independent per-tab view contexts, using the existing graph resolver and descriptor.
2. Enable real closable graph tabs, then unify Files/System and supported source graphs into one resource-based workspace.
3. Continue generic descriptor-renderer consolidation and explicit verified/unknown execution flow, including side effects and exceptions.
4. Improve large-graph layout, minimap, docking, and edge readability with real Qt screenshots.
5. Qualify a second read-only language adapter; only then broaden guarded visual source-edit transforms with round-trip tests.
