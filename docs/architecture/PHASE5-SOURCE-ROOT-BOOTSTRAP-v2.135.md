# v2.135 — Deferred binding for the first protected Python source-root open

## Reproduction and owner boundary

The original source root may have no `GraphViewSession` even after a
secondary resource tab transitions into a source view. In that state,
`_open_navigation_route` formerly changed `_active_source_tab_id` to the
uninitialized root **before** `_open_python_source_path` proved the requested
file could be opened. A rejected file therefore left Qt showing the original
resource root but rebound the active source editor/aliases to a root with
no document. This is a transaction-ordering error, not a missing tab
abstraction.

## Alternatives

- A: restore the old source aliases after failure. Rejected because it is
  compensating rollback code and can overwrite editor state changed during
  a failed source load.
- B: reuse the **same existing** `_open_python_source_path` preflight and
  defer the protected-root alias switch until that preflight succeeds.
  Selected. A private `bootstrap_root` argument preserves the initial-root
  compatibility contract without another source writer, parser, tab registry,
  navigation owner, or duplicated preflight.

## Consequences and verification

The existing source opening method obtains presentation detail from the
target root view when bootstrapping, resolves the file and Python graph
exactly as before, and only then stores the outgoing secondary view and binds
the protected root. The original root continues to own the first `source`
GraphViewSession. Direct file-picker opening, invalid-source text diagnostics,
source-owned revisions, independent secondary history, and source publication
semantics are unchanged.

`tests/test_v2135_root_bootstrap_atomicity.py` asserts correct ordering
and retention of the existing route transaction. Native
`QT_STAGE uninitialized-source-root-bootstrap-refusal` uses a separate
real NativeLab window to transition a resource secondary into Python while
the source root is uninitialized; it injects a bounded source-open refusal
and verifies no alias/editor/session/owner change. A valid retry must then
open the protected source root without destroying the secondary session.

No ADR or global architecture changes. Revert this targeted preflight
binding order to v2.134 on regression. GitHub headless/native CI and an
independent Linux Mint host report remain the required qualification gates.
