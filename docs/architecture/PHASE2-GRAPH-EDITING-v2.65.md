# v2.65 — Integrated graph-owned interaction and document lifecycle

## Grounded baseline

v2.64 host-qualified on WolfCat-Studio: `qualification-20261030-231138-128731.tar.gz`, 759 headless PASS and four independent native Qt PASS markers. v2.65 changes have headless coverage but require a separate native host report.

## Decisions and alternatives

- Extend the existing `ProgramGraph.edit()` authority, **not** editable Qt node dictionaries or the separate legacy Draft model. Signature edits and data property edits use its revisioned commands, preserving atomic validation, persistence, and undo/redo.
- When dropping onto an occupied input, **replace that input wire in one transaction** (keep its edge identity); reject separate disconnect/connect because an interrupted operation could leave an unintended disconnected state or two undo entries. Structural validation still rejects invalid direction, scope, or relation.
- For graph-owned **Save As**, make a new program identity via `ProgramGraph.save_as()` and publish through the original guarded saver, then rebind the active Qt tab only on success. Reject overwriting an existing file/symlink. Reusing the same root identity for two independently editable files was rejected.
- Function names are Python identifiers, not keywords. Interface definitions remain structural until the Python adapter explicitly qualifies parameter types, defaults, and callable semantics.
- Primitive Literal editing accepts JSON scalar values. No Python expression evaluation, side effects or implicit execution occurs on input.

## Acceptance evidence and limitations

Headless `tests/test_v265_graph_authoring.py` covers function and parameter changes, duplicate/keyword refusals, transaction rollback, single-revision wire replacement and identity, Save As fork/symlink refusal, safe failure, round-tripping and GUI contract. `qt_smoke.py` program subprocess also tests these capabilities through the real ProgramWorkspace on Linux. Native Qt pending.

Known limitations: no Python lowering, graph/source synchronization, effect semantics, arbitrary input defaults, function-call nodes, comment editing, graph debugger, complete keyboard navigation or large graph virtualization. `ProgramGraph` remains a persistable incomplete programming document, not an executable language. Full Python-first Blueprint usability and compiler qualification remain in canonical queue.
