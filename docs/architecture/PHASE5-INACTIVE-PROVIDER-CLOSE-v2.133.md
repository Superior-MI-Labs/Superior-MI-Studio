# v2.133 — Closing inactive last-active provider tabs preserves foreground

## Observed root cause

Qt tab selection is the authority for foreground presentation; `_active_source_tab_id`
and `_active_resource_tab_id` are compatibility aliases for the most recently
active view *of that provider*, not the currently selected global page.
`_close_graph_tab` correctly rebound a removed last-active provider ID to its
protected root, but **always called `tabs.setCurrentWidget(root.page)`**.
Closing an inactive secondary source tab from a selected resource root, or
vice versa, therefore stole foreground focus and could disrupt the other
provider's in-progress navigation/camera presentation.

## Alternatives and decision

- A: replace provider aliases or tab registry entirely with a general
  workspace controller. Rejected: adds state ownership and migration risk.
- B: keep provider-specific cleanup unchanged, but condition Qt foreground
  selection on whether the page being closed was actually selected at entry.
  **Selected.** This modifies the existing close path, no new source of truth.

## Contract and tests

`_close_graph_tab` records `closing_selected = tabs.currentWidget() is page`
using Qt's real membership before removal. It always closes the intended
`GraphViewSessions` entry, saves its camera, removes its provider view,
and rebinds a now-absent provider alias to that provider's protected root.
It selects that root **only** if the removed tab had the foreground. Closing
an inactive last-active alias preserves the different provider's selected
page, history, document owner and camera. ProgramWorkspace confirmation and
both root-close refusals are unchanged.

`tests/test_v2133_foreground_close_policy.py` characterizes the guard, and
`QT_STAGE inactive-other-provider-close-preserves-foreground` exercises
both source→resource and resource→source inactive-close cases in real Qt.
These tests complement, rather than replace, existing current-tab close,
unsaved-source teardown, root-anchor, provider-transition and camera tests.

## Acceptance and rollback

The complete headless gate plus GitHub native Qt smoke must pass. Independent
Linux Mint native host evidence is required for installation promotion.
Revert this isolated close policy to v2.132 if any active-tab closure, route,
source draft, or camera regression appears. No ADR/non-goal change.
