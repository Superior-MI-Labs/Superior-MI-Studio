# v2.149 — Legacy developer tab visibility honors selected Qt foreground

## Failure and user impact

After native ProgramGraph commands became the ordinary file workflow,
`toggle_legacy_graph(..., visible=False)` still unconditionally called
`activate_source_tab()` after hiding a legacy developer tab. A user could
uncheck an inactive prototype page while editing a native graph or browsing
resources, and their active document would be replaced in the foreground
by a source compatibility alias. That alias can point to a secondary
source tab rather than the protected source root.

## Alternatives and selected correction

1. Add a general workspace tab-controller/lifecycle registry to take over
   close behavior: rejected. The Qt page and existing provider registries
   already supply identity; another layer duplicates ownership.
2. In-place correction: distinguish whether the *actual* legacy Qt page
   was selected before removal. If not, leave the foreground untouched.
   If it was selected, activate the exact protected source-root page from
   `_source_tabs['source'].page`. Selected. Existing graph/root and
   provider state are retained.

The prototype JSON model and developer tabs remain supported under ADR-014.
No source/graph transaction, parser, page registry, or route owner changes.

## Acceptance and rollback

- `tests/test_v2149_legacy_foreground.py` checks the selected-page gate,
  source-root fallback and absence of new tab/session ownership.
- `QT_STAGE legacy-visibility-preserves-selected-document` checks
  actual menu toggle-off while a native ProgramWorkspace is selected,
  while a resource root is selected, and while a source secondary alias
  exists before an active developer page is closed.
- Require full headless doctor and GitHub native offscreen Qt qualification.
  Linux Mint host qualification remains separate; revert this batch
  if Qt foreground, source revision, history or camera regresses.
