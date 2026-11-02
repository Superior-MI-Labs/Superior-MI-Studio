# v2.26: Independent filesystem graph tabs

## Qualification baseline

The v2.25 WolfCat-Studio report `qualification-20261029-051554-225737.tar.gz` records 368 passing headless tests, `NATIVE_QT_SMOKE_PASS`, and ten diagnostic screenshots, including `independent-graph-tabs.png`. That is the host-qualified baseline. v2.26 is not natively Qt-qualified until the new smoke passes on Linux Mint.

## Architecture decision

**Two approaches rejected:** (a) clone the resource provider or directory graph into a second persistent authority for every tab; (b) keep one resource canvas and change only the labels/history to simulate multiple tabs. Both contradict the existing source-of-truth and camera contracts.

**Chosen:** Extend the existing `GraphViewSessions`, `Route`, `resolve_graph`, `GraphCanvas`, `GraphViewportHost` and `QTabWidget` with a small `ResourceTabView` presentation context. Each resource tab has a real canvas, breadcrumb toolbar, camera identity, history, current directory, bounded page offset, expanded-directory set, and import-overlay preference. The provider still owns filesystem evidence. The graph and descriptor are disposable projections, not persisted source or filesystem state.

`NativeLab`'s resource fields remain *active-view compatibility aliases*, just as source fields remain aliases during the staged migration. A canvas's camera key now resolves from its own session route, so an inactive canvas cannot accidentally save the active tab's file/directory identity. The shared presentation store still owns the camera values. The preexisting application-owned minimap layout remains unchanged.

## Interaction

- Double-click a directory node: expand/collapse it inline, preserving the current directory tab.
- Ctrl + double-click a directory: open that directory in an independent, closable graph tab.
- The Graph menu offers **Open current directory in new tab**.
- Back/Forward, parent, breadcrumb, directory paging, and nested expansion affect the selected resource tab.
- Ctrl + double-click a Python file continues to open a new source tab. Ordinary `.py` opening still reuses the active Python view; this is intentionally not yet the full unified route-changing tab.
- Closing a resource tab closes only its view; nothing is deleted or executed. The initial Files/System tab remains retained until universal workspace consolidation.

## Root-cause guardrails and tests

- `browse_resource` now resolves the proposed route and graph *before* clearing expanded paths, so unsupported/missing destinations cannot partially mutate view state.
- Per-canvas camera lookup follows the session identity for source and resource views, including when saving inactive tabs during window shutdown.
- The native Qt smoke exercises two live filesystem tabs, cross-tab camera isolation, directory navigation and history, a rejected route, tab switching, minimap host containment, closing, and continued source-tab identity.
- Three new headless tests exercise the actual route/descriptor/session pipeline for resource-tab independence, failed-route nonmutation, and resource/source camera separation. `doctor.sh` is the mandatory headless release gate.
- Unknown languages, mutable filesystem actions, bidirectional node-to-source editing, independent control-region tabs, and non-Python programming adapters remain **not qualified**. No source interpreter runs just from opening a graph.

## Follow-on work, in order

1. Qualify the new resource tabs on WolfCat-Studio. Do not declare full GUI success from the headless suite.
2. Remove the remaining active-view compatibility aliases from Qt rendering and editing, replacing them with an explicit current `GraphViewContext`/resolved descriptor access path. Prefer upgrading the existing `GraphViewSession` contract over a parallel registry.
3. Allow one selected graph tab to change from filesystem-resource route to source-language route while retaining its camera and history, then retire the special permanently allocated Files/Python root tabs. Make normal double-click navigate the same tab; Ctrl+double-click opens another.
4. Continue renderer descriptor unification, Python call/effect semantics, exceptional control paths, and guarded reversible visual-to-source edits. Keep speculative execution out of the graph.
5. Qualify one read-only second-language adapter against the same renderer and routing contract. Large layout and docking improvements follow real screenshots, not guesses.
