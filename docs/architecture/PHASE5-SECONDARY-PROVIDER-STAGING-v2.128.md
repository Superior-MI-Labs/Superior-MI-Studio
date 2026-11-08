# v2.128 — Stage secondary-provider Qt replacements before retiring the old view

## Architecture decision

The single `GraphViewSessions` session still owns route/history and the existing
`SourceTabView` / `ResourceTabView` registries own view preferences. `GraphCanvas`
and Qt widgets remain non-authoritative projections. Protected root tabs remain
intact; no new tab coordinator, view cache, parser, or source document is added.

Two approaches were evaluated:

- **Replacement transaction framework:** add an independent tab manager with
  rollback/commit semantics. Rejected: duplicates view and history authority.
- **Prepare then publish in `_transition_graph_tab`:** resolve provider, history
  and old-page membership first, construct the replacement graph page and
  toolbar without publishing it, then perform the existing transition.
  Selected: narrows the real failure window and reuses established contracts.

## Verified boundary

Before v2.128, the old provider registry was deleted and root aliases changed
*before* replacement Qt page and navigation-toolbar construction. An exception
in `_create_navigation_bar` could strand the old selected tab without its
registered view. v2.128 stages `GraphCanvas`, its page, provider-specific view,
its toolbar and label before writing `self._source_documents`, saving cameras,
changing aliases, deleting a registry entry or advancing history. A specific
`RuntimeError` or `ValueError` during staging reports refusal and deletes only
the discarded staged page. Unexpected failures are not silently swallowed.

A new native Qt stage intentionally fails toolbar construction and asserts
that the selected page, active aliases, source-document map, registry view,
route/history and camera remain unchanged. It then confirms the original
cross-provider action succeeds. Headless tests enforce ordering and native
stage presence, but cannot substitute for native widget evidence.

## Scope and limitation

This corrects **preparation failure** only; the later Qt remove/insert and
canvas rebuild still follow the existing implementation. Do not claim full
exception-atomicity for arbitrary Qt callbacks. The next navigation cleanup
must use the same parity gate before retiring more compatibility branches.

## Qualification

Run `bash scripts/agent-verify.sh --headless` and test the native Qt smoke on
Linux. A passing GitHub native-Qt lane does not certify the Linux Mint host.
The latest uploaded Linux Mint native report remains v2.124 until new evidence.
