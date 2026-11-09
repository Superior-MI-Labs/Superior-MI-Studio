# v2.132 — One selected-view alias binding path

## Existing behavior and duplication

The Qt tab-change callback, breadcrumb/location routing and same-provider
history navigation all found the selected source/resource view through the
same `_graph_tab_for_page`, but each separately repeated conditional
`_store_active_*` and `_activate_*` calls. Source activation additionally
flushed the pending analysis timer only in the tab-change signal. This
created three subtly diverging ways to synchronize temporary window-global
active-view aliases with the current graph page.

## Alternatives

- A: rely entirely on QTabWidget.currentChanged. Rejected: direct route or
  history operations can run on an already-selected Qt page without another
  tab-change signal, especially after cross-provider replacement.
- B: preserve the established provider-specific store/activate methods and
  reuse them through one private idempotent `_bind_selected_graph_view` reader.
  **Selected.** This is not a new owner/controller or mutable session; it
  delegates to exactly the existing view and source-document systems.

## Invariants and scope

For selected resource/source views, matching active session IDs must be
no-ops. Changed IDs save previous presentation preferences then bind the
incoming provider view; source changes flush existing pending live-analysis
first. The same route-resolution, document draft, history, and graph camera
owners remain unchanged. The original unbound source root remains a
protected compatibility anchor; its explicit first-file adapter can bind a
non-selected root and therefore is intentionally **not** folded into this
selected-page helper. Legacy prototype canvases and ProgramWorkspace are
not affected.

`tests/test_v2132_view_alias_binding.py` characterizes code-level ownership
and call-site consolidation; `QT_STAGE selected-graph-view-binding-idempotence`
rebinds actual resource/source roots without mutating their history, camera,
selected page, active alias identity or shared source document. Both new and
existing native stages are required for acceptance.

## Stop/rollback rule

The native Qt stage and full headless gate must pass on GitHub; a passing
Mint host report is separately required to promote an installation.
If tab selection, source editor draft, navigation history, or camera
integrity breaks, revert this bounded adapter consolidation to v2.131.
No ADR changes; existing authority contracts remain in force.
