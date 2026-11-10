# v2.136 — Source-root navigation selects filesystem root, not a stale provider alias

## Reproduced ownership gap

The selected Qt page can be the protected original Python source root while
`_active_resource_tab_id` still identifies the last-used **secondary**
filesystem tab. Before v2.136, `_open_navigation_route` called
`browse_resource(route.path)` with no target identity for both cases.
That command would resolve a directory using the secondary's expansion and
relationship preferences and commit to its history, then show that secondary
page. The original filesystem root was not the navigation destination.

## Alternatives

A. Rebind the resource root before calling `browse_resource`, then restore
aliases after a failure. **Rejected:** the wrong provider might be selected
on an error, and rollback would be another shadow transaction.

B. Reuse the existing resource projection and history owner with a
`root_anchor` option for the protected source-root case. **Selected:**
the target root's view preferences are read for the normal `resolve_graph`
preflight, with no alias mutation. Only a successful resolution stores the
last-active secondary view, binds the original resource root, updates its
existing session and rebuilds its canvas. When the replacement graph is
already qualified, `_activate_resource_view(reproject=False)` avoids
re-reading the previous root path or refreshing stale chrome before commit.

## Invariants

The same-kind resource paths and secondary cross-provider transition keep
their original dispatcher. The original root IDs and close guards are
untouched. There is no new graph, document registry, navigation controller,
AST, writer, or route authority. Missing directories fail without changing
the foreground Qt page, resource aliases, route history, camera, expansion
or active source. Valid source-root-to-directory navigation updates only
the protected resource root. Independently navigable secondary resource tabs
retain their existing route, camera and source evidence.

`tests/test_v2136_resource_root_route.py` checks the dispatch, preflight,
alias binding, and no-extra-provider-resolution contracts.
`QT_STAGE source-root-resource-anchor-isolation` is a real Qt regression
with root and secondary resource pages, refused directory and successful
root navigation, then a return to the secondary page and its closure.

Rollback to v2.135 if a supported navigation path changes unexpectedly.
GitHub headless and offscreen Qt CI do not replace Linux Mint host proof.
