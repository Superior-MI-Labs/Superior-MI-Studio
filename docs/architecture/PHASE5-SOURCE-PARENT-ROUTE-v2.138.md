# v2.138 — Source "Up" action reuses selected graph tab navigation

## Observed bypass

v2.136 corrected the shared `_open_navigation_route` for the original
source-to-filesystem root. The legacy `source_go_parent()` toolbar command
still called `browse_resource(self.python_doc.path.parent)` directly from
whole-file mode, ignoring the selected Python tab's GraphViewSession.
When the user was working in a secondary Python graph, that bypass could
replace an unrelated last-active filesystem tab instead of returning the
**same** secondary graph tab to the parent directory.

## Alternatives

A. Add another `root_anchor` branch directly inside `source_go_parent`.
**Rejected:** this would duplicate navigation policy, remain incorrect for
secondary source tabs, and create yet another maintenance point.

B. Construct the existing `Route('resource', parent_path)` and delegate
to `_open_navigation_route`. **Selected:** one dispatch already knows the
difference between protected root and secondary cross-provider transition,
validates before mutation, and preserves tab-local history/camera. Focused
source scopes continue using `navigate_source(parent_scope)` unchanged.

## Invariants and tests

- An original whole-file source root goes to the protected resource root,
  not a last-active secondary resource alias.
- A secondary whole-file source view transitions to resource provider
  **in the same tab**, retaining Back to the exact source document route.
- Neither protected root route nor another secondary tab's route changes.
- No additional registry, resource index, compiler, source editor, or
  navigation history is created.

`tests/test_v2138_source_parent_route.py` checks the exact dispatch,
mode-specific behavior and original root/secondary route policy.
`QT_STAGE source-parent-uses-selected-graph-session` verifies a real
secondary resource→Python→parent resource→Back journey, source/root isolation,
and safe secondary tab closure.

Rollback to v2.137 on navigation regression. GitHub native CI is an
early gate; Linux Mint host qualification is still mandatory.
