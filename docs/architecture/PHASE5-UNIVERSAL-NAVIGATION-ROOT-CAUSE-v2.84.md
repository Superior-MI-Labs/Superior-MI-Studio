# Phase 5 / v2.84 — History and live source route root-cause analysis

**Status:** candidate; headless verified, Linux native Qt pending. Latest fully native-qualified baseline is v2.81.

## Evidence and failure mechanism

The 2026-11-02 uploaded v2.83 host report fails in `QT_STAGE universal-tab-live-source-and-scope`, at the second `resource` Forward (`qt_smoke.py:2051`). The test had first navigated to the unsaved function's focused route, then navigated Back to the directory, changed the shared source owner to invalid syntax, and correctly verified Forward refusal. It next replaced the live source with the *original saved revision*, whose function is named `before`, not `unsaved`, while expecting Forward to the now-missing `unsaved` scope to succeed.

This is a **test-oracle defect**: the application correctly rejects unknown scope identities. The earlier v2.82 failure occurred on the same scenario. v2.83's selected-page change addressed another possible history-owner mismatch, but it could not make an invalid destination valid.

## Approaches considered

1. Silently fall back to the Python module overview (or translate renamed scopes by position), and let Forward succeed. **Rejected:** changes the navigation destination while advancing a history cursor for a different route; can display the wrong semantic identity and restore a camera for a different function.
2. Throw away history when a source scope disappears. **Rejected:** unnecessary loss of user navigation and no ability to revisit when a draft is repaired or undone.
3. Preserve stale history entries but validate the target against the exact current `SourceDocumentSession` revision before any history/tab/camera commit. **Chosen.** A route may remain in history without being currently navigable. Reintroducing the exact scope makes the route reachable again.

## Consolidation

Both `_transition_graph_tab` and `_navigate_source_document_in_tab` now use `_resolve_live_source_route`. The reusable `graph_routes.resolve_source_session_route` enforces source owner identity and a valid parsed revision, then delegates to the existing `resolve_graph` provider. It **cannot** fall back to disk parsing when `owner.parsed` is None. Source history for same-file and cross-file destinations shares this preflight path. No second source owner, graph model, parser or history stack is introduced.

The native scenario now proves: valid source focus, Back to resource, invalid draft refusal, valid-but-deleted scope refusal, restoration of matching scope and successful Forward. Headless tests cover cursor/camera immutability, dirty source vs disk, wrong owner rejection, source-to-source session continuity, and structural use of the unified preflight.

## Remaining risk

Native Qt has not been exercised in the release authoring environment; the Linux host must run v2.84's complete doctor and Qt suite. If it fails, retain the old installation and upload the full qualification archive. The v2.84 diagnosis does not imply all future navigation defects are fixed, only that this repeated failure is now characterized and protected by coherent tests.
