# Phase 5: Focused visible-file relationships (v2.91)

## Decision

One-hop file-relationship exploration is a *presentation filter* on the existing read-only `resource_graph.directory_graph` projection. It is not a search index, parser, source owner, navigation registry, or runtime dependency analyzer. This phase rejects a new per-project graph database or eager directory crawler because the existing bounded visible graph is already the authoritative scope of candidate edges.

## Behavior

- Focus a file card from its context menu or from the resource toolbar selection. Focus either endpoint of a validated resource relationship from the existing Inspector or edge context menu.
- Show only outgoing source relationships, incoming references to the file, or both. Layer selection (`imports` and `references`) intersects with the focus; it is independent of direction.
- The directory snapshot continues to display all visible files, with no unrequested recursive traversal, added file nodes or hidden dependency resolution. A candidate must already pass the existing static Python import / literal reference evidence checks. Synthetic symbol annotations remain non-executable.
- A focused file must be one of the actual file cards in the currently resolved snapshot, under the root without any symlink path components. A missing or hidden target refuses qualification; source sessions still override closed source bytes and invalid drafts suppress stale relationships.
- Tab-local preferences (`relationship_focus`, `relationship_direction`) are stored alongside the existing per-tab overlay and layer choices. Changing directory or page clears focus; toggling overlay visibility preserves it. All edge refreshes read the validated owning canvas render revision. No second tab registry or graph authority.
- Focusing changes presentation only. No navigation history, file buffer, filesystem state, ProgramGraph, camera identity or publication pipeline is mutated. The Inspector is cleared when a focused projection replaces its graph revision, invalidating previous edge IDs.

## Verification gates

- Headless: incoming/outgoing/both; no focus; intersection with imports and literal references; Python and non-Python endpoints; empty neighborhood; active source draft; hidden/child/external/missing/symlink rejection; overlay off/on; contract validity.
- Native Qt: file-card and Inspector focus actions, direction toggles, per-tab independence, temporary overlay hiding, delayed inactive-canvas `update_edges`, and no uncaught Qt callbacks.
- Full release: doctor and Python/ProgramGraph gates, version/manifest integrity, isolated installer, then real host Qt smoke before old-install cleanup and launch.

## Non-goals

Transitive dependency inference, third-party import execution, package-wide or repository-wide indexing, new document editors, hiding unrelated nodes, or making mutable graph relationships from syntactic candidate edges.
