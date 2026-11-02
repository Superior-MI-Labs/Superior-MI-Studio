# Phase 5: Inspecting visible workspace relationships (v2.89)

## Decision

**Reuse the existing graph contract, selected tab and Inspector panel.** A separate file dependency database or a new graph/editor framework would create a second source of truth and exacerbate the previous inactive-tab edge crash. Instead, pure `inspect_resource_relationship(contract, graph, edge_id)` validates one resource edge against the exact graph revision that the selected `GraphCanvas` rendered. Edge description and source-line evidence come from the immutable `GraphDescriptor`; endpoint paths come from the matching visible resource nodes after identity/hash, root and symlink guards.

## Gestures

- Select a file relationship edge or right-click its wire to inspect source, target, certainty, and bounded provenance in the existing Inspector. The display deliberately says that a syntactic association is not proven at runtime.
- Open source/target actions use `_open_navigation_route` and its existing graph sessions and history. Python resources open with their source owner. Non-Python resources navigate to their visible parent directory; no generic writable editor is inferred.
- The source/target buttons fail closed if a tab switches away, the edge disappears, the rendered graph is modified, or an endpoint is replaced with a symlink.

## Safety and scope

Do not read project file contents when inspecting a wire. Do not execute Python or resolve imports dynamically. Do not recursively index resources or follow symlinks. Rendering is only evidence of a visible syntactic association. An old inspection must not drive navigation after its canvas ceases to be the selected revision.

## Tests

`tests/test_v289_relationship_inspection.py` exercises candidate provenance, both relation types, graph-revision mismatch, forged edge/node paths, hidden/nonvisible targets and symlink races. `QT_STAGE resource-relationship-inspector-and-actions` exercises selected-tab Inspector use and endpoint navigation; the existing inactive-render stage also refuses inspection from inactive canvases. Native qualification must run on the target Linux/Qt host before promotion.
