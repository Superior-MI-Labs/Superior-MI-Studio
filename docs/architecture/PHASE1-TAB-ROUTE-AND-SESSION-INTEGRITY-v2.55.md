# v2.55 — Phase 1 route and document identity repair

## Verified host failure and evidence

The supplied `qualification-20261030-213845-6207.tar.gz` for v2.54 passed its doctor gate but failed native Qt smoke at `QT_STAGE revisioned-source-session`. The Python traceback identifies `studio_native/gui.py::open_resource_in_new_tab` attempting `_view_sessions.open(sid,route)` where `route` was never bound. The resource provider already returned `ResolvedGraph.route`; all subsequent tab labeling used that resolved identity. No parser, source editing or installer fault is established by this traceback.

## Architecture decision and alternatives

- **A — create a new `Route` from the directory path at UI publication.** Duplicates provider route normalization and risks a separate camera/history identity. Rejected.
- **B — publish `resolved.route` from the existing `resolve_graph()` provider.** Selected. One verified route controls the independent resource tab's session, graph and tab title. This corrects the undefined local without a parallel route owner.

Review also found that `reload_python_source()` replaced `_source_documents[path]` with a new `SourceDocumentSession` when the old one was dirty. That violates the shared document-identity contract for multiple tabs. Now `discard_and_reload(discard_unsaved=True)` is called only after existing user confirmation; it reads and validates replacement before changing the same session object. The default still refuses dirty reload. No file is written by reload, no source code is executed, and failed reads preserve unsaved text.

## Qualification

- Headless AST regression verifies resource tab publication uses provider-qualified `resolved.route`; a separate provider/session test checks independent camera identities.
- Source-document tests verify explicit discard updates the same object referenced by multiple views, refusing implicit discard and retaining the buffer on missing-file errors.
- Qt smoke adds `QT_STAGE independent-resource-tab` before the actual directory-tab operation, so this owner has a distinct host diagnostic stage.
- Native PyQt6 is unavailable in the packaging sandbox. This change is not Linux-GUI-qualified until the user supplies the real v2.55 host report. Headless PASS is insufficient for promotion.

## Non-goals and next gate

No new parser, compiler, graph registry, source writer, or language adapter. Do not begin graph-owned authoring or claim unified text+graph undo while the source-session native lifecycle remains unqualified. After host PASS, characterize cross-tab buffer undo, external-change indicators/merge choices and recovery before expanding the document migration. Rollback is the preserved v2.54/v2.53 package if native qualification fails. ADR changes: **none**, this repair enforces ADR-001, ADR-010, ADR-015 and ADR-016.
