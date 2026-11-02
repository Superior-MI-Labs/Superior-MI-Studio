# v2.22 — Active graph routes must agree with the rendered graph

## Host failure

The WolfCat-Studio report `qualification-20261029-041307-223264.tar.gz` failed at the final native Qt camera isolation test, after taking ten screenshots. It compared focused and whole-file root-camera keys, but both keys belonged to a previously focused function (`module/function:sum_items:11:0`). This is a state ownership defect, not merely a faulty test assertion.

## Root cause

`GraphCanvas.graph_camera_key('@root-view')` properly delegates root-camera identity to `GraphViewSession.camera_slot()`. However, `_display_source_route(...,record_history=False)` changed `source_scope`, `source_view_mode`, and `source_graph` without updating the session. After displaying Whole File, the session continued advertising an older focused route. It could therefore restore, read or overwrite a camera under the wrong identity. The parallel filesystem history path also committed its history move only after rebuilding.

## Decisions and changes

- **Reject UI camera-key overrides** derived from source flags. That would introduce a second authority and defeat the v2.20–v2.21 session work.
- **Keep one navigation-history authority** with three explicit operations: `visit` (normal new navigation), `replace_current` (refresh/new display without adding a Back entry) and `move` (validated Back/Forward traversal). No second active-route cache or duplicate camera map.
- `GraphViewSession.activate` validates and commits the resolved destination before graph/camera rebuild. It refuses mismatched history destinations and only mutates history after the adapter successfully resolves the graph.
- Both resource browsing and Python focus/whole-file routes use this transition path, including history traversal. Source reload also synchronizes the route to the new document snapshot.
- A same-route refresh leaves the Back/Forward history intact. Replacing the current entry with a different unrecorded route discards forward history so there is no ambiguous branch.
- The Qt smoke checks route and camera keys on focus -> whole -> focus and Back/Forward, in addition to existing geometry, minimap, docking and source checks.

## Qualifications and limits

- Packaging environment: full Python doctor, compilation, and 358 headless tests passed (352 baseline + 6), fresh archive extraction and isolated installer rehearsal.
- No native PyQt6 is present in the packaging environment. **The Qt regression is not qualified** until the actual Linux host runs `RUN-ALL.sh` and supplies the report.
- No change to Python AST analysis, semantic contracts, source edits, node authoring, execution semantics or unrelated layout.

## Ongoing roadmap

1. Complete session ownership of canvas context (source identity, route, camera, selection) without cloning documents.
2. Real independent, closable graph tabs; then unify filesystem resources and supported source-language views.
3. Descriptor-driven rendering, provenance and verified versus uncertain execution channels.
4. Large-graph presentation and a second read-only language adapter.
5. Only then guarded visual-to-source editing and round-trip qualification.
