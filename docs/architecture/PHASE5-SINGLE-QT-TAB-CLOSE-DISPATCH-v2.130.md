# v2.130 — One existing Qt page-to-view authority for tab closure

## Alternatives

(A) Add a new tab-registry/controller to handle close, provider transitions and
history. Rejected: would duplicate the existing `GraphViewSessions` and Qt page
registration, increasing drift risk. (B) Use `_graph_tab_for_page()` for closing
as already used by navigation, tab activation, inspectors and canvas actions.
Selected B; no new state or framework.

## Change and invariants

`_close_graph_tab` previously traversed `_source_tabs.values()` and then
`_resource_tabs.values()` independently to locate the page being closed,
while other tab operations already used `_graph_tab_for_page(page)`. This
repeated page lookup could diverge as the graph-provider migration evolved.
The single lookup now returns the actual SourceTabView, ResourceTabView, or
ProgramWorkspace and dispatches to the **same existing close branches**.
Original resource/source root anchors remain protected; the graph session
closes only the targeted secondary session; ProgramWorkspace confirmation
remains unchanged; closing a source projection never destroys its text owner.

A native stage closes an inactive secondary resource page while the protected
root page is selected, and verifies root selection, registry, route/history,
and camera remain intact. The existing full native smoke continues to exercise
program close confirmation, source and resource tab creation and closure,
cross-provider transitions, dirty source ownership and original root guards.
Three headless tests enforce the dispatch and root guards; they are not a
substitute for native Qt evidence.

## Qualification

Run `bash scripts/agent-verify.sh --headless` and GitHub native Qt CI, followed
by independent Linux Mint native host verification before promotion. v2.129
GitHub CI passed both lanes, but the latest uploaded Linux Mint PASS is v2.124.
