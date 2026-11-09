# v2.131 — Stage secondary Qt tab creation before owner/session publication

## Observed duplication

The v2.128–v2.129 migration corrected premature registry mutation when an
existing **secondary** Qt tab changed providers. Creating an entirely new
secondary resource or Python tab retained a parallel lifecycle mistake:
`open_resource_in_new_tab` and `open_source_in_new_tab` registered their new
session/view (and the source branch published its text owner) **before**
constructing the navigation toolbar. If that Qt construction failed, the
selected tab and its view registry could diverge or contain a ghost session.

## Options and decision

- A: create a generic tab-transaction manager to own staging and all views.
  Rejected because `QTabWidget`, `GraphViewSessions`, `SourceDocumentSession`
  and provider-specific view maps already own the relevant state. A manager
  would be an overlapping authority without sufficient benefit.
- B: use the existing provider-specific constructors and stage their Qt
  canvas/page/toolbar before updating the existing registries, counters,
  source owner map or navigation history. **Selected.** The original
  initial/unbound source root is not modified by this patch.

## Invariants and tests

When building a new resource or initialized-source tab, failure constructing
its toolbar must dispose only the staged Qt page and leave the selected
page, existing source documents, view maps, route histories, camera slots,
active aliases, tab numbers, and protected root tabs unchanged. A subsequent
valid opening must still succeed under the next unused session ID. New tabs
still use the same `GraphViewSessions` and QTabWidget publication. No extra
source buffer or parser is created; opening a project never executes code.

Tests: `tests/test_v2131_new_tab_staging.py` (static lifecycle contract)
and the real `QT_STAGE new-secondary-tab-staging-refusal` in
`studio_native/qt_smoke.py`, including fault injection for both providers
and successful open/close recovery. Run the complete headless verification,
then GitHub native Qt and independent Linux Mint host qualification.

## Non-goals / rollback

This addresses construction failures before registration; it is **not** a
blanket claim that subsequent arbitrary Qt event or renderer exceptions are
recoverable. The first-ever source-root file-opening adapter remains intact.
If native Qt stage or existing source history/camera parity fails, revert
this isolated lifecycle change and keep the previous v2.130 candidate.
No ADR definition changes; existing ownership and non-goals remain in force.
