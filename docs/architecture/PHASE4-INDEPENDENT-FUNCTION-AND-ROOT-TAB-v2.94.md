# v2.94 — Root tab identity repair and independent function reconciliation

## Host failure root cause

The 2026-11-02 v2.93 Linux integration test passed the relationship explorer but called `_close_graph_tab(w.tabs.currentIndex())` twice after creating multiple resource tabs. The Qt current selection changed after the first close, so the second call deleted session `resource`. The production close guard used only the count of resource tabs, which allows deletion of the root while other tabs exist. Subsequent tests relied on `_resource_tabs['resource']` and failed.

The correct policy is to protect the two original compatibility session IDs until a deliberate workspace migration removes their special status. This is a production invariant, not a test workaround. Native smoke now closes exactly its own created page identities and probes the guarded root close while extra tabs exist. The model registry and route owners are unchanged.

## Independent Python source reconciliation — bounded first slice

An existing `SourceDocumentSession` owns independently authored text. The user explicitly chooses a `ProgramGraph` function by its exact name. A pure AST read locates exactly one top-level source function; other source regions (including unrecognized code) are not projected into the graph or rewritten. A synthetic candidate replaces only the selected function in the current generated graph baseline, and the existing `_qualified_source_edit_plan` proves all changes via full compiler re-lowering. `ast.unparse` is used **only for an internal, never-saved proof candidate**; it does not reformat the user's source.

Review returns stable source revision/hash, graph revision, explicit function name/line span and node operations. Import is separate, requires the exact receipt, checks live disk and document state and re-runs the same proof, then commits a single undoable graph transaction. The source file remains untouched; unknown constructs remain outside graph semantics. This is not arbitrary independent Python conversion, automatic linking, or fuzzy identifier matching.

## Qualification gates

- Headless: positive review/import, atomic undo, unrelated code retention, stale source and graph revision refusal, duplicate definitions, changed signatures, unsupported statements, invalid syntax and external file mutation.
- Native: explicit root tab close refusal while a secondary tab is present, exact created-page cleanup, independent function Review/Import with source unchanged, and all preexisting Qt stages.
- Release promotion: headless doctor + ProgramGraph/Python gates + integrity + native Qt on WolfCat-Studio. Retain v2.90 if the host rejects v2.94.
