# v2.134 — Program-owned tabs are not resource/source navigation sessions

## Observed defect

`_graph_tab_for_page` returns `ProgramWorkspace` for a native graph-owned
document. `_open_navigation_route` accessed `selected.session_id` before
checking the selected view type. `ProgramWorkspace` deliberately has no
`GraphViewSession` identity; an ordinary route raised `AttributeError`
rather than cleanly refusing unsupported in-place navigation.

## Alternatives

- **A: add a fabricated session ID to ProgramWorkspace** or introduce a
  universal tab controller. Rejected: would make graph-owned documents pretend
  to be source/resource routes, creating false ownership and migration debt.
- **B: enforce the existing provider type boundary** before reading
  `selected.session_id`. Selected: one guard in the existing dispatcher,
  no new state or writer, and no change to explicit new-tab navigation.

## Acceptance and scope

An in-place source/resource route from a native ProgramWorkspace or legacy
non-provider tab must refuse without mutating the Qt foreground, provider
aliases, source owner map, graph revision, navigation histories or cameras.
Explicit `new_tab=True` still goes through the existing view creator.

`tests/test_v2134_program_navigation_boundary.py` checks the provider
identity contract and guard ordering. Native Qt stage
`program-owned-navigation-refusal` exercises both refusal directions from
a saved ProgramWorkspace, confirms unchanged owner/state, then opens and
closes an explicit new resource tab. No new registry, parser, source writer,
tab controller, compiler semantics, or ADR change.

Rollback: revert this typed guard to v2.133 if native Qt shows an unexpected
supported navigation path. GitHub headless/native CI and independent Linux
Mint host qualification remain separate acceptance gates.
