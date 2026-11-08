# v2.129 — Destination registry owns each staged provider transition

## Observed failure

The v2.128 headless suite passed 1,375 tests, but GitHub native Qt failed
reproducibly in `resource-evidence-line-and-file-framing`. A diagnostic CI run
showed the selected replacement as `SourceTabView`, but
`_active_source_document()` returned `None`. The graph history had advanced to
the expected Python path while the old editor path remained loaded. Root cause:
`_transition_graph_tab` staged the replacement correctly but then chose the
**old provider type** to register the new view. It stored a new `SourceTabView`
inside `_resource_tabs` on resource→source navigation (and vice versa).

## Correction and responsibility boundary

Do not add another tab registry or compensation framework. The same existing
`_graph_tab_for_page`, `GraphViewSessions`, `SourceTabView` and `ResourceTabView`
remain responsible for view identity, routes and presentation. Distinguish:

1. **Old provider kind** — decides which previous view registry loses the
   existing secondary tab.
2. **Destination `route.kind`** — decides which provider registry receives the
   fully prepared replacement view.
3. `session.activate()` advances one history only after correct registration.

The Qt smoke retains a failure-only line-evidence diagnostic (no new runtime
behavior) and checks both provider directions, exact owner and active aliases.
`test_v2129_provider_destination_registry.py` characterizes the two separate
branches so later cleanup cannot accidentally recombine them.

## Test and promotion gates

Headless tests are structural evidence and cannot prove Qt event-loop behavior.
GitHub native Qt must pass the evidence-jump stage, the injected toolbar
construction refusal, and all later integration stages. Linux Mint native
promotion remains independent; the last uploaded host PASS is v2.124.

The next close-tab consolidation should reuse `_graph_tab_for_page` and change
no graph authority, but is held until v2.129 native CI is green.
