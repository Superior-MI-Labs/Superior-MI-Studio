# v2.29 Architecture review: Blueprint lessons, graph input policy, and eventual source round-trips

Date: 2026-10-29. Baseline: v2.28, host-qualified 385 headless tests plus NATIVE_QT_SMOKE_PASS (qualification-20261029-061335-228580). This memo is an engineering decision record, **not** a claim that bidirectional visual authoring is implemented.

## What this release actually changes

- `GraphCanvas.navigation_surface` routes default middle-drag through the **existing** Qt-selected owner nodes. A hovered child graph is not automatically the pan target. If its owner is selected, it takes the pan; otherwise its selected ancestor does, falling back to the root. Ctrl continues to pan root; Shift continues to pan the hovered parent explicitly. No new selected-graph preference, persisted flag, or source mutation.
- `graph_surface.selected_pan_surface` is a pure policy function. Nested arbitrary-depth and deselection tests run without Qt. The native Qt smoke now selects and deselects a real expanded composite to test the actual hit-tested target; host qualification is required.
- No Python AST, source editing, normalized descriptor, return-routing, graph navigation, or connection-authorization changes. Future visual-programming semantics must not be invented by the renderer.

## Findings against Epic's Blueprint model

Official references (accessed 2026-10-29):

- [Graphs](https://dev.epicgames.com/documentation/unreal-engine/graphs-in-unreal-engine)
- [Nodes / collapsed graphs / tunnel interfaces](https://dev.epicgames.com/documentation/unreal-engine/nodes-in-unreal-engine)
- [Flow control](https://dev.epicgames.com/documentation/unreal-engine/flow-control-in-unreal-engine)
- [Collapsing graphs, functions, and macros](https://dev.epicgames.com/documentation/en-us/unreal-engine/collapsing-graphs-in-unreal-engine)
- [Connecting nodes and type compatibility](https://dev.epicgames.com/documentation/unreal-engine/connecting-nodes-in-unreal-engine)

Blueprint uses a Branch as a control *operation*: one execution input, boolean condition, True/False execution outputs. A For Loop is another operation with Body and Completed execution paths plus index/data pins. A Function is a reusable callable graph with entry and result, and its caller has a separate call site. A Collapsed Graph is a *graph organization* mechanism; input/output tunnels communicate with the parent graph. Macros are reusable collapsed networks. Those categories are not interchangeable.

Our Python adapter currently produces genuine `branch` and `loop` operations, but `PythonDocument.composite_file_graph` also assigns `child_region_key` and `region_role` directly to these nodes and the Qt renderer grows the operation card into a container. Focusing lexical functions preserves the same operation identity, but inner `if`/loop body regions do not yet have first-class focus routes. That explains why the program can feel different in focused and nested layouts even when the underlying source node IDs remain stable. This is **the design debt to resolve before graph-to-source authoring**.

## Decision for the eventual canonical interface

1. **Keep one graph semantics**, independent of zoom, focus, collapse, tabs, or minimap. Node/port/edge identities do not depend on UI state.
2. **Represent conditionals as operations, not graph wrappers by default.** An IF adapter construct yields a Branch-style control operation, condition dependency, True/False successors, and source-backed region membership for each arm. The body can appear in the same focused surface. An optional explicit grouping/collapse view hides its child operations without changing the Branch's authored meaning. `elif` is a new conditional on the False path, *unless* the source adapter provides a more specific construct that round-trips exactly.
3. **Keep loops as atomic control operations with source-backed body membership**, break, continue, else and completion (where applicable). These are not blindly identical to Blueprint For Loop; Python `for` iterates an iterable, supports `else`, break, exceptions, and async variants. The adapter owns this difference.
4. **Use true nested graphs for callable/function implementations, explicitly authored organizational collapsed graphs, and resources containing other resources**. A presentation-only expansion of a Python region may remain as an optional inspection view, but must not become a separate compiler/program identity.
5. **Separate execution, data, references, region containment, and exceptional exits**. White exec triangles/wires are shown only with verified control relations. A Python call expression's data result does not prove purity; short-circuit expressions, generator suspension, exceptions and side effects require adapter evidence. Unknown remains unknown, never drawn as a certified path.
6. **Keep a single per-tab view context** for cameras, history, selection, and focus. The file-system hierarchy and AST lexical hierarchy share navigation UI but not semantic ownership rules.

### Two alternatives evaluated

A. Preserve auto-expanding every IF/loop node into a nested graph and add focus and camera rules. Less near-term work, but conflates an operation with a container, complicates visual pin edits and code round-trip, and burdens dense source graphs with micro-viewports. **Reject as the authoring default**.

B. Keep Branch/Loop operations and program control regions distinct, while preserving optional grouping and a common focus viewer. It matches the useful Blueprint convention and scales better across languages. It does require a versioned region/edge contract and a migration of existing Qt presentation logic. **Choose for future structural migration**, after a round-trip pilot qualifies the schema.

## The missing library/catalog layer

There is already a prototype Node Lab `model.py` and a source analyzer with syntax nodes. These are **not** a universal visual-programming catalog or a code generator. Do not add a second globally authoritative node registry beside `semantic_contract` and the language adapter.

Target a single provider/adapter-backed operation catalog whose *descriptors* include: stable operation ID; language and version; port contracts; control paths; type relations; binding/evaluation semantics; effect certainty; region roles; supported source transforms; provenance requirements; and (where qualified) emit/parse round-trip capabilities. The UI library is a filtered **view of this catalog**, not another source of node definitions. An adapter can advertise operations it actually understands and decline unsupported constructs. We should not attempt to pre-enumerate every operation in every language.

Language-neutral core kinds: data value/reference, binding read/write, call, branch, iteration, return/raise/yield, scope/definition, region/group, resource. Each has language-specific variants. Python `and/or` short-circuit evaluation, C++ lifetime, Rust ownership, JS async, and other semantics must remain adapter-defined and cannot be silently translated into generic "exec wires".

## Proposed guarded text-to-graph-to-text pipeline

1. Parse a real source file with the language's authoritative parser; capture exact source spans, tokens/comments where supported, stable semantic identities, scope/symbol binding, region ownership, and diagnostics. Do **not** execute imported code to visualize it.
2. Project immutable graph descriptors and typed relationships; reveal unknown effects explicitly. Rendering, mini-map, selection, and collapse are not authoring data.
3. Visual editing chooses a known adapter-catalog operation with a declared transform. Validate port direction, typing, control dominators/ordering, symbol references, source scope, and editability. If any requirement is unknown, refuse with a diagnostic.
4. Generate a *proposed* AST/token-level source edit, preserving unaffected formatting and comments. Show reviewed diff. Reparse, validate syntax, reproject the graph, and verify the intended change with semantic/invariant tests. For supported transforms compare the normalized pre/post graph excluding allowed changed identities; avoid claiming full semantic equivalence for arbitrary programs.
5. Save atomically with a hash/stale-file check and backup. One source authority remains. Undo and diagnostics must use the same edit transaction.

**First authoring pilot, not a broad compiler**: within one Python function, insert a literal + comparison + if/else with two supported branches; then change a literal, undo it, and delete a branch through validated source patches. Run text->graph->text->graph regression cases, including comments, nested scopes, early returns, and incompatible pins. Refuse ambiguous transformations. This validates the catalog and structure before accepting arbitrary drag-to-program connections.

## Release qualification gates

- Host v2.28 report: 385 tests / native Qt PASS.
- v2.29: six new pure pan-selection regressions, plus a real Qt scene selection test added to `qt_smoke.py`.
- Pending WolfCat-Studio: verify middle-drag root vs selected region, Ctrl root, Shift hovered parent, nested child-selected behavior, and no source/graph identity mutation. A GUI smoke PASS does not prove the proposed visual-authoring architecture is implemented.

## Roadmap, preserving the original priorities

A. Qualify this selected-pan interaction; complete universal cross-provider tabs, remove last window-global source/resource aliases.

B. Stabilize descriptor-controlled region semantics and renderer. Split operation control flow from view-region containment. Migrate old IF/loop presentation without losing source/port/edge IDs or guarded edits. Prefer one renderer, not special per-language node subclasses.

C. Implement read-only catalog discovery from the existing adapter and a deliberately small Python source-to-graph-to-source editing pilot. Do not build generic graph-to-code emission without a proven language transform.

D. Add a second read-only language adapter after the shared contract and tests are qualified, then expand catalog operations and guarded transforms by language capability.
