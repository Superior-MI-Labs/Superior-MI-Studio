# Phase 5 / v2.82 — Universal tab transitions preserve source authority

**Status:** headless release candidate, native Linux Qt pending. **Rollback:** v2.81 host-qualified (`qualification-20261102-000205-33043.tar.gz`).

## Alternatives

1. Add a universal tab registry, clone Python documents on provider changes, or maintain separate source previews in resource tabs. **Rejected:** introduces duplicate authoritative state and a second navigation pipeline.
2. Reuse `GraphViewSessions`, `resolve_graph()`, `SourceDocumentSession` and the existing `_transition_graph_tab()`. **Chosen:** only change how the destination is resolved and where embedded resource-node open actions are dispatched.

## Invariants and change

- Resource→source on a secondary tab first looks up `_source_documents` for an exact canonical path. Any unsaved revision wins; clean sessions with external file modifications reload *in place*, matching ordinary source open. A new source session is created through `_new_source_document()` (including recovery checks), but registered only once the provider accepts the graph route.
- Invalid current source revisions and missing focused scopes do not produce graphs or advance navigation history; the old tab stays put. Source owned bytes are never written to disk through this navigation path.
- A file card, embedded source symbol or directory card passes its `Route` to `_open_navigation_route()`: Ctrl+open creates another view, normal open in a secondary resource tab retains the same session ID, view history and camera ownership. The retained primary source/resource tabs continue to provide compatibility anchors.
- Native Qt tests check source ownership, live drafts, unsaved disk preservation, scope focus, Back/Forward, and rejected navigation. The existing headless suite still qualifies semantic graph contracts. No new parser/editor/store/compiler/renderer was introduced.

## Follow-up

Remaining root-tab special cases and same-kind activation paths should be consolidated only after actual UI parity checks. Broader cross-folder indexing or inline graphical editing is explicitly outside this release.
