# Phase 5 / v2.83 — Selected-tab history and same-provider navigation

**Status:** candidate, headless and archive gates required. Native Qt must pass on WolfCat-Studio before promotion; **v2.81 is the rollback**.

## Incoming evidence and decision

The uploaded v2.82 Linux report (`qualification-20261102-002148-33860.tar.gz`) contains `NATIVE_QT_RECOVERY_PASS`, `NATIVE_QT_DOCUMENT_PASS`, `NATIVE_QT_PROGRAM_PASS`, but `QT_STAGE_FAILED integration-subprocess exit=1` after `QT_STAGE universal-tab-live-source-and-scope`. In the new live-draft scenario, Back to resource succeeded and Forward to source asserted. This invalidates the v2.82 qualification claim. Root diagnosis: history dispatch derived its session from window-global active-provider aliases, which can change while a secondary tab is being replaced with another provider. The selected Qt page owns session membership; provider aliases are only temporary view bindings.

## Competing approaches

1. Add a new universal tab manager, clone source documents per route, or patch the smoke to ignore failed Forward. **Rejected:** duplicate route/source authorities and loss of real regression protection.
2. Keep `GraphViewSessions` and existing provider-specific canvases, but select the session from the actual tab page, preserve the same session on source→source, and validate destination in the source owner before committing a route. **Chosen.** A secondary source view can now visit another Python file without replacing its history stack; a dirty owner remains intact.

## Boundaries

- `QTabWidget` page membership chooses the current session for Back/Forward. The view-session history still owns the route cursor; Qt never owns semantic state.
- Source-to-source route selection first uses the existing `SourceDocumentSession`; parsed invalid drafts cannot fall through to `resolve_graph(..., document=None)` because that resolver intentionally accepts `None` as disk-open for other callers.
- Both source and resource graph providers retain separate graph descriptors. Switching pages cannot create Python files, execute code, save unsaved drafts, merge different source owners, or replace the graph-owned ProgramGraph document.
- Same-tab source navigation preserves the session ID, route-camera identity and Back/Forward; opposite provider transitions retain their existing validated transaction.
- New native smoke tests exercise unsaved text across resource↔Python↔resource, focused scopes, source A↔source B, disk-modified dirty sources, invalid Python and refused history, and per-tab cleanup. Headless tests assert route identity and projection contracts. These tests do not substitute for native Qt evidence.

## Deferred

No new tab framework, language extension host, broad cross-folder relationship index or general Python reconciliation in this release. Continue root-tab alias cleanup only after real Qt parity evidence is collected.
