# v2.13 — Universal graph location and navigation history

## Problem and actual baseline

The user supplied Linux file-manager breadcrumb screenshots and a source graph `icon_hint → if not icon_id → if role in (...) → elif role == 'loop'`. They want clickable ancestry, back/forward/up, address toggle, one compact top row, expanded graphs as independent tabs, and eventually one unified resource/software navigator. The current program has two graph canvases, single mutable Python source view state and distinct filesystem/AST/control-region containment relations. A UI-only merge of Python+Files tabs into independent sessions would be dishonest: old `window.python_doc`, `source_scope`, `source_graph` and `source_view_mode` would be shared.

## Alternatives

A. Put a new global path string in each toolbar, switch graphs on click and duplicate the Python graph if the user wants tabs. **Reject**: misleading 'filesystem path' for AST regions, second navigation authority, scope collisions, and shared-camera corruption.

B. Add one small immutable `Route` value and crumb/history projections derived from existing providers and `PythonDocument.scopes`. Give each existing canvas the same thin navigation control, then move view state into per-tab `GraphViewSession` before permitting multiple independent tabs. **Chosen**: meaningful immediate capability with a stable future contract.

## Implemented

- `navigation.py` has Qt-free immutable resource, source and future region route identities. Breadcrumb labels are presentation only; source scope keys come from the Python adapter and resource paths from `Path`/the resource provider. Invalid source scope navigation refuses, rather than guessing.
- `NavigationHistory` keeps bounded view-only back/forward entries; history advances only after an operation succeeds. Failed filesystem traversal does not alter route history.
- `NativeLab` uses one navigation toolbar builder for Python and Files tabs, with source-specific or resource-specific controls behind one trailing menu. The full file ancestry appears in Python breadcrumbs. Very long paths collapse intermediate crumbs into an accessible menu.
- In Python the address field is read-only because a file path plus lexical scope is not necessarily a filesystem address. Files address mode accepts directories via `browse_resource()` and does not bypass its existing safety checks. There is no embedded code execution.
- The host Qt regression exercises source crumb QAction signals and back/forward, FS history and address editing; the standard report saves `breadcrumb-navigation.png`.

## Explicitly not implemented

- Arbitrarily deep *control region* focus. `PythonDocument.scopes` models modules, classes and functions; IF/ELIF/loop body `child_region_key` represents presentation containment, not a lexical scope. Future region route focus must project a source-backed region into its own graph session, not forge a new AST scope.
- Multiple Python graph documents open in parallel or independent per-tab cameras. Do this only after moving Python source state out of `NativeLab` into one `GraphViewSession` per tab and reusing the same renderer/descriptor pipeline.
- Dock-area autohide/hover or cross-language adapters. They are subsequent staged work.

## Regression and next priorities

`./doctor.sh`: 302/302 headless tests pass (+5 navigation tests), Python compilation and syntax checks. The native Qt smoke source includes new breadcrumb and history assertions, but it cannot run in this environment because PyQt6 is unavailable. The code must not be considered GUI-qualified until the user's Mint host report passes.

Next: (1) validate Qt host screenshots and fix any navigation toolbar overflow issues; (2) consolidate descriptor-driven presentation and audit remaining Python special cases; (3) implement `GraphViewSession` with one owner per document/canvas and a single adapter/route resolver; (4) enable opened file/region tabs, shared history and precise source editor selection per session; (5) accurate execution/effects and additional read-only adapter; (6) Qt-native dock-area controls without introducing widget-level duplications.
