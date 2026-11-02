# v2.28: Compact breadcrumbs and cross-provider tab migration

## Qualification baseline

The supplied `qualification-20261029-054609-226569.tar.gz` records `NATIVE_QT_SMOKE_PASS` for v2.27. Its doctor ran 376 tests. This new release requires its own Linux host Qt smoke; the packaging environment does not contain PyQt6.

## Architecture decisions and alternatives

1. **Rejected:** A second breadcrumb/path hierarchy or a fresh universal-tab controller. Both would duplicate the existing `Route`, `GraphViewSession`, route resolver, Qt tab registry, and camera source of truth.
2. **Chosen:** Evolve the existing breadcrumb presentation and reuse one session across provider transitions. On additional tabs, resolution happens before swapping the underlying Qt view. Session identity and history remain constant. Source bytes and filesystem metadata still belong to the original providers. The original two root tabs remain available until their remaining global compatibility fields are retired.

## Changes

- Added pure `shorten_crumb` and `visible_breadcrumbs` projections to `navigation.py`. Formatting cannot modify route identity. Label limit is 22 characters with both ends visible; show first and last two routes with full intermediate ancestry in a dropdown. Tooltips retain full path and name.
- Applied compact Qt stylesheet only to the navigation toolbar, and reduced general button, tab and dock-header padding modestly. Navigation controls now use fixed compact widths.
- Added `NativeLab._transition_graph_tab` to navigate a secondary tab between `resource` and `source` views. It retains the same `GraphViewSession` and camera slot namespace and creates no cloned source authority or alternate graph resolver. The existing provider view type is replaced in Qt while root tabs stay available as compatibility anchors.
- Breadcrumb dispatch, directory file activation and history movement all use that transition boundary for cross-provider routes on secondary tabs. Same-kind provider navigation continues via existing code.
- Added nine headless tests for routes, truncation, Unicode, invalid destinations and contract ownership. Native smoke exercises directory -> Python -> Back -> Forward, invalid destinations, tab identity/close, minimap ownership and screenshot capture.

## Known limits and next releases

- Cross-provider same-tab navigation is currently enabled only for **additional** tabs. Root tabs still follow existing dedicated paths to avoid breaking older window-global state. This is an explicit incremental migration, not a claim that the permanent split UI is finished.
- Additional source file swaps through the old file-opening method may still reset earlier same-kind history. The next consolidation should retire window-global aliases and route *all* tab navigation through one provider-independent operation.
- Qt interactions must pass native Linux smoke before claiming host qualification. The source adapter, return semantics, guarded edits and unknown-effect analysis are unchanged.
- Preserve the wider roadmap: generic descriptor-based renderer; verified execution and call/return semantics; node-to-source edits with reviewed diffs and round trips; then qualified read-only adapters for additional languages. Do not add language-specific Qt widgets.
