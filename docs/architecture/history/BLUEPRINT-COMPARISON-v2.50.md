# Superior MI Studio v2.50 vs Unreal Engine Blueprint

**Architecture and interaction review — October 30, 2026**  
**Input:** `Superior-MI-Python-Visual-Programming-Lab-v2.50.zip`  
**Method:** local static code inspection, headless tests and sample Python graph projections, plus Epic Games' public Unreal Engine Blueprint documentation and C++ API reference. No Unreal Engine source checkout, running Unreal Editor session, or native PyQt6 window comparison was performed. Recommendations are engineering judgments; exact Unreal internal behavior is cited only where publicly documented.

## Executive conclusion

Superior MI Studio has an appropriately conservative architecture for a **source-authoritative, multi-language, text-and-visual IDE**. Blueprint is a **graph-authoritative programming system** compiling its graph asset to executable bytecode. A verbatim Blueprint implementation would solve the wrong problem: it would enable arbitrary visual edges while endangering source parity. Studio should borrow Blueprint's *interaction contracts*, not its graph-as-program authority.

The largest gap is not node decoration or missing icons. It is **interaction completion**: the user must be able to begin a valid source-backed operation through a consistent gesture, understand what it will do, receive accurate validation feedback, and complete the edit without hunting through multiple disconnected UI surfaces. The second major gap is a limited set of qualified, reversible Python transformations, especially direct execution-flow editing. The third is graph complexity and maintainability: large embedded recursive surfaces and a single 5,108-line `gui.py` create risk relative to small, focused per-scope editors.

No new runtime, graph compiler, semantic node registry, or general-purpose type system is recommended for the next milestone.

## Direct inspection and verification

- The archive contains ~14,000 lines across 30 Python implementation modules, including `gui.py` (5,108), `qt_smoke.py` (1,720), `python_graph.py` (1,566), and `python_authoring.py` (1,531). Module counts are approximate, excluding documentation and tests.
- Local command `python -m unittest discover -s tests -q` completed: **606 tests, OK**, approximately 3.6 seconds on the analysis host.
- `python scripts/python-first-gate.py` completed successfully and produced its graph parity summary. It validates a bounded subset, not arbitrary authoring or runtime semantics.
- PyQt6 is **not installed** here; I did not run `qt_smoke.py` or a native QGraphicsView event simulation. The project's own README says **v2.50 native Qt is not yet qualified**, after a stalled earlier host smoke.
- `python_authoring.definitions()` advertises **19** qualified Python source operations. That is more than an empty proof of concept, but not general direct manipulation of syntax or control flow.
- `python_graph.py` limits single-source files to **1.5 MB** for analysis, function graph views to **220 nodes**, and nesting to **24**. The whole-file view gives a truncation warning. These are protective prototype bounds, not production-scale graph behavior.
- Sample projections I constructed: simple function `param + 2` yielded 6 nodes/6 edges; a function containing a stored effectful call yielded a Call node and source-derived data edges; `return a and b` remained one **opaque BoolOp** node; `async def` with `try`/`await` was represented with an **opaque Try** statement; Python `for/else` with break generated loop, branch, break and return control representation. These were parse/projection inspections only, not end-to-end GUI demos.

## Unreal architecture: what each layer owns

| Unreal public API | Role | Studio analog and limit |
|---|---|---|
| `UEdGraph` | Owns nodes, schema, graph identity and subgraphs | `PythonDocument.scope_graph()` creates a transient graph from saved code; source remains authoritative |
| `UEdGraphNode`, `UK2Node` | Node type, pins, behavior, node expansion for compilation | AST node projection, `NodeDescriptor`, Python lowering functions; no executable graph nodes |
| `UEdGraphPin` | Direction, type, default, unique identity and links | `PortDescriptor` validates labels/types/directions, and adapter-produced payloads carry source semantics |
| `UEdGraphSchema`, `UEdGraphSchema_K2` | Connection compatibility, promoted connections, conversion, context actions, reconstruction | `source_connection.inspect_connection()` invokes real source rewrite preflight; `semantic_contract` validates graph channels |
| `SGraphPanel` / `SGraphNode` / `SGraphPin` | Rendering, gestures, previews, selection | Qt `GraphCanvas`, `NodeItem`, `PortItem` |
| `FConnectionDrawingPolicy` | Geometry/styling, hover and highlights, relink/slice | `edge_presentation.edge_style()`, `GraphCanvas.update_edges()`, source previews |
| `FBlueprintActionDatabase` | Provider-independent spawnable action inventory | `python_authoring.definitions()` projected through `operation_catalog.qualified_operations()` and `authoring_actions.available_actions()` |
| `FKismetCompilerContext`, `FNodeHandlingFunctor`, `FKismetTerm`, `FKismetCompiledStatement` | Graph lowering, dependency scheduling, statements/terms and bytecode back end | Studio instead emits guarded source changes, reparses saved Python, and delegates execution to normal Python |

**Why the split matters:** Epic's GraphEditor is not tied to one scripting graph. The schema changes what may connect, while the same editor framework can present Blueprint, material and other graphs. Studio's semantic contract plus Python adapter follows the same principle in a source-authoritative setting. Continue that separation without imitating UObject, C++ reflection or Blueprint's bytecode system.

### Graph IDs, reconstructions and view state

Unreal uses persistent graph/node GUIDs and supports pin reconstruction, with orphaned-pin metadata. Studio's Python node IDs often derive from lexical scope plus line/column/end positions (`python_graph.py`, expression IDs at ~946), while `presentation_state.py` persists node layout by those IDs. Insertions above a statement can invalidate display identity. Do **not** add generated semantic IDs to Python source just to retain layout. Instead use a conservative, versioned layout-reconciliation algorithm matching source path, lexical scope, statement role, structural fingerprint and nearby spans, then refuse ambiguous matches. Presentation state must remain non-semantic.

## Comparison of the editor's human-facing interaction system

| Interaction | Unreal Blueprint | Studio v2.50 | Implication |
|---|---|---|---|
| Place node | Right-click/keyboard contextual actions, action database, pin-drop search | Searchable 390×300 modal `QDialog`, Node Library buttons and qualified pin-drop | Common authority is correct, but interruption and breadth are worse |
| Connect existing nodes | Drag pins, valid/invalid feedback, compatible conversions where supported | Draft graph accepts same-type links; source graph preflights a real guarded Python edit and shows hints | Correct semantics; affordances and coverage lag |
| Call/expression output as source | Ordinary compatible pin gesture | Backend supports restricted call/operation/compare outputs; Qt gesture-start excludes them | **Concrete mismatch** in capability surfacing |
| Reconnect/break a wire | Dedicated pin actions, relink, break, reroute | Source edits are limited; source-view `Delete` is deliberately disabled | Major usability gap, must be solved by source transformation, not fake graph edge |
| Execution vs values | Separate white exec vs colored typed data; pure/impure distinction | White control pins, typed value pins, effect-unverified Call nodes and conservative control edges | Good direction; Python semantics rightly differ |
| Default input | Unconnected pins expose type-specific value widgets | Draft defaults; source literal editing via direct double-click; expression preview chips | Reuse existing port semantics, make inline editing more discoverable |
| Navigation | Tabs, breadcrumbs, My Blueprint, collapse, find, frame/zoom | Tabs, breadcrumbs, graph regions, symbol browser, minimap, Home, right-pan, marquee | Considerable parity, though embedded surfaces can impair legibility |
| Large graph readability | Functions, collapsed graphs/macros, comments, reroute and wire highlighting | Recursive/nested graph canvases, compact nodes, colored/dashed relation wires, limited annotations | Make focused per-function graph the default; retain whole-file as overview |
| Undo and history | Editor undo transactions | v2.50 bounded committed Python undo/redo with stale-file checking; separate presentation state | Strong source safety, but not unified graph edit/move undo |
| Debugger | Breakpoints, watched pins, flow animation, call stacks | Syntax check and opt-in normal Python subprocess; no integrated graph debugger | Important IDE maturity gap, not a reason to build a custom Python interpreter |

### Verified capability mismatch: source backend vs drag gesture

`python_edit.rewire_source_operand()` explicitly admits source nodes of kind `literal`, `param`, `assignment`, `operation`, `compare` and `call`, subject to structural, dominance and safety conditions (`python_edit.py:265+`). `source_connection.inspect_connection()` delegates to this routine. In tests such as `test_v238_expression_and_keyword_wiring.py` and `test_v239_stored_call_result_connections.py`, a constant-only expression result or uniquely stored Call result can be valid source for a target rewrite.

Yet `GraphCanvas.mousePressEvent()` near `gui.py:1894` only starts a source output drag for `literal`, `param`, or certain `assignment` nodes. Thus a user cannot initiate an ordinary drag from output types that the backend accepts. The older v2.39 implementation notes claim a Call→consumer native drag was added, so the current code warrants a targeted regression rather than trusting that historical claim. **Do not fix this by adding another type switch to Qt.** Expose one adapter-qualified `can_start_connection()`/source capability query, reused by cursor, interaction start, hover, menus and native tests. The actual target legality must continue to use `inspect_connection`.

### Wire geometry and interaction

Studio already draws cubic Bezier connections in `GraphCanvas.make_curve()` and detoured loopbacks in `make_loopback_curve()`. `update_edges()` reconstructs source-derived edge objects and handles graph boundary mirrors, folded Return facets, cross-region z-order, source evidence tooltips and relation styles. `edge_presentation.py` centralizes wire colors, widths and styles. These are sound choices.

Unreal uses `FConnectionDrawingPolicy`, which supports hover deemphasis, selected pins, relink previews, wire intersection testing and specialized policies. Studio lacks established parity for **reroute control points, breaking source wires, moving existing links, hover highlighting a connected subgraph, connection insertion, and obstacle-aware routing**. Add presentation-only reroute metadata before attempting sophisticated automatic routing. A reroute must reference an existing source-backed edge by stable identity and cannot create new semantics. Where source edits can legitimately reconnect, show green acceptance, precise refusal and a preview of the proposed change. Where they cannot, keep the wire visible but mark it as read-only.

### Nested surfaces, Return and graph scopes

Studio has put considerable effort into recursive embedded graph surfaces, boundary mirrors, inner zoom/camera, source Return facets and non-local exit rendering. This is a sophisticated presentation layer, but it is also an ergonomics and geometry liability: nested viewports create more competing pan/resize/drag surfaces and require special cross-boundary wire painting. Unreal instead gives first-class focused function/event graphs with navigation and organizational collapsed subgraphs. Studio should default to a **readable focused function** and treat whole-file nesting as an optional overview. Reuse the existing routes, tabs and view sessions; do not implement another canvas.

Studio properly distinguishes a Python function definition from an invocation. Return sites and the function result boundary are source-owned interfaces rather than fabricated executable nodes. This is important. No extra Return edges or synthetic call execution should be introduced simply to resemble a Blueprint screenshot.

### Python is not Blueprint

- Blueprint's pure nodes have a declared contract; Python operator overloads, properties, function calls and even apparently simple reads can have observable effects.
- Python `and`/`or`, chained comparisons and conditional expressions are short-circuit/lazy; translating their arguments into eagerly computed independent node outputs can change results.
- Python evaluation is ordered and can raise exceptions; reusing a Call node's expression in two places may execute the call twice. Studio's stored-local qualification is a necessary rule.
- Python control constructs including `try/finally`, `yield`, `await`, pattern matching, comprehensions, dynamic imports, decorators and closures need their own language adapter rules. Studio currently preserves many as opaque rather than lying about the execution graph. That is correct.
- Python names can be rebound and aliases are dynamic. A wire is therefore not automatically a permanently valid type-checked runtime dependency. `py:unknown` should remain the honest default when proof is unavailable.

## Concrete engineering issues, with evidence

**P0 / UX authorization drift:** Backend supports restricted Call/operation/compare connection sources, while Qt output drag start disallows them (`python_edit.py:265+`, `gui.py:1894+`, `tests/test_v238_*`, `tests/test_v239_*`). Route gesture eligibility through adapter-owned capability. Include real Qt tests.

**P0 / end-to-end proof:** Passing 606 headless tests does not qualify native mouse behavior. v2.50 native Qt smoke is currently unverified by this analysis. The project's own readme documents a previous modal-test hang and corrective timeout handling. Require the actual host smoke, screenshots, no Python tracebacks, and hands-on creation/editing exercise.

**P1 / high friction for ordinary programming:** The action list is bounded to 19 operations and most creation occurs through modal forms and source diff review (`authoring_actions.py`, `gui.py:3056+`). Maintain review and safe source changes, but allow a direct in-graph transaction that previews a compatible operation and displays a concise before/after edit. For simple, proven transforms, consider an opt-in reduced-friction confirmation with undo; do not silently write unsafe edits.

**P1 / source wire editing coverage:** Source `Delete` is disabled in `GraphCanvas.keyPressEvent()` and source wire rewiring is restricted (`python_edit.py`, `gui.py:2111+`). First qualify one full operation round-trip: create → connect → reconnect → disconnect → delete → undo/redo → save/reopen. The graph must agree with saved code after every step. Start with straight-line function bodies, bounded assignment and Return wiring.

**P1 / transparency of unsupported code:** Opaque projection is honest but users need explicit tooltips/diagnostics showing why an operation cannot be edited and whether it is read-only due to semantics, missing transform, invalid source, unsaved buffer or ambiguity. Link each visible restriction to a specific producer-owned rule.

**P1 / view mode complexity:** Whole-file recursion and in-node graph viewports solve a real overview need but introduce camera, clipping, boundary and edge-layer complexity (`GraphSurfaceItem`, `NodeItem`, `GraphCanvas`, `graph_surface.py`). Default to focused function editing, keep whole-file as overview, and test keyboard/mouse consistency at every depth.

**P1 / UX identity continuity:** Source-derived IDs are location dependent while persisted node positions are keyed by IDs. Build conservative, presentation-only migration. Test source insertions, formatting-only changes, function rename and ambiguous duplicate expressions.

**P2 / growing Qt concentration:** `gui.py` is 5,108 lines, ~36.5% of the 13,978 Python implementation lines. Do not rewrite the framework; extract bounded interaction/event policies and dialogs from the current file only when a specific change is otherwise risky. Prefer consolidating existing helpers, not a collection of new controllers.

**P2 / run/debug tools:** The app offers a warning-gated normal Python subprocess and syntax checks (`gui.py:4267+`), not integrated breakpoints/watch traces. When needed, integrate an existing debugger protocol and Python tooling rather than instrumenting code in the graph renderer or claiming safe execution.

**P2 / scalability:** `python_graph.py` enforces 220 nodes per focused function and 1.5 MB per file. Measure projection time, node/edge redraw, hover qualification and tab switch on increasing graph sizes before removing guardrails. `GraphCanvas` can rebuild paths for entire edge collections; optimize only after profiling shows it matters.

## Architecture choice: evaluated approaches

### A. Full Unreal-style graph authority

An independent mutable graph would make arbitrary node dropping, pin connection and graph undo easier. But converting *every* valid state into semantically equivalent Python — and eventually Rust/C++, etc. — is a much harder unsolved contract. This creates competing authorities for source and graph, ambiguous edits after text changes, and graph structures with no valid source lowering. **Reject for Studio's current mission.**

### B. Source-authoritative graph projection + explicit edit intents (recommended)

Keep `.py` as the programming authority. Let the adapter map source → graph, describe eligible operations, build a proposal for a user intent, validate it, preview the expected graph/source change, atomically save approved source with stale checking, and reparse. The Qt view should never decide language legality. Reuse `semantic_contract`, `source_connection`, `python_authoring`, `python_edit` and `SourceEditHistory` rather than creating another operation engine.

This retains Studio's differentiator: text and visual editing share one truthful program, with clear unsupported boundaries and portability to other language adapters.

### C. Temporary draft graph as canonical intermediate (defer)

A detached graph editing sandbox would allow temporarily invalid connections, but it entails a second synchronization protocol, mismatch handling, dangling edits and another truth source. It may eventually be useful as *ephemeral edit intent staging*, but no persistent canonical draft-program should be introduced now.

## Suggested phased implementation with acceptance criteria

**Phase 0: Host qualification and permission UX (no new features).** Run v2.50 `RUN-ALL.sh` on Linux/Qt with bounded timeout; capture real interaction screenshots, verify no callback exceptions and modal hangs, inspect graph/return pin visibility, right-pan, marquee and top-layer selection. Run a manual task from empty Python source through visual function creation and save. Gate release on both tests and human observed behavior.

**Phase 1: Consolidate gesture eligibility.** Have `source_connection` or the adapter expose stable discovery of source output candidates, distinct from connection acceptance. Wire the Qt initial click, hover cursor, pin-drop menu and hint layer to one eligibility contract. Demonstrate real Call→consumer and constant-operation→consumer drags already supported by the backend, plus red feedback for unsafe effects. No new node kinds.

**Phase 2: One complete editable slice.** Choose a small straight-line function: create function → add variables/expressions → connect → reconnect → disconnect → delete → undo/redo. Implement only source transforms that can be semantically proven. Use the current source proposal pipeline, preimage guards, exact diff, backup and reparse. Add fixtures with comments, CRLF, UTF-8, external edit races, shadowing and exceptions. Show unsupported operations distinctly instead of silently failing.

**Phase 3: Readability.** Make the focused function editor the default. Add presentation-only comments and reroute controls, selected-pin connected-wire highlight and connection refusal explanations. Keep whole-file overview and the existing minimap, tab routes and cameras. Benchmark 50/100/200-node graphs and nested viewports. Resist adding a second UI system.

**Phase 4: Broader semantics after the gates pass.** Signature changes across callers, control flow edits for branch/loop paths, safer multiple Return sites, async/exception behavior, and Python tooling integration. Only after this is stable should a second language adapter be trialed against the same contracts.

## Critical acceptance tests

1. A valid stored Call result is draggable from the actual Call output in a live Qt window; source contains exactly one original Call invocation after connection.
2. A constant-only arithmetic output is draggable and yields one exactly matching source proposal; a runtime/side-effectful arithmetic output is refused.
3. Branch true/false, loop body/completion, loop `else`, break/continue and multiple Return exits remain faithful after drawing, collapsing and navigating.
4. Reconnecting a qualified input emits one approved source edit; undo/redo restores exact program behavior and source bytes. External disk modification blocks stale undo.
5. One origin node may supply multiple consumers without duplicated evaluation of an effectful producer.
6. Unsaved text, mismatched tabs, stale source, ambiguity, dynamic dispatch and unknown types produce truthful UI refusals.
7. Source edits adding lines above nodes preserve unaffected presentation positions only when matching is unambiguous; no lost or misapplied positions.
8. Every editable capability is discovered consistently through Node Library, right-click, Tab search and pin drag, with one adapter action authority.
9. Actual Linux Qt qualification exercises drag, hit testing, labels, nested clipping, minimap, dialogs, keyboard accelerators, source writes and no traceback/timeout.
10. A user unfamiliar with the application can author and change a small multi-function program visually and explain why each displayed wire corresponds to an actual source relationship.

## Direct official Epic references

- Blueprint Editor graph & controls: https://dev.epicgames.com/documentation/unreal-engine/graph-editor-for-the-blueprints-visual-scripting-editor-in-unreal-engine
- Placing nodes / contextual search: https://dev.epicgames.com/documentation/unreal-engine/placing-nodes-in-unreal-engine
- Connecting nodes / reroutes: https://dev.epicgames.com/documentation/en-us/unreal-engine/connecting-nodes-in-unreal-engine
- Shortcut and gesture cheat sheet: https://dev.epicgames.com/documentation/unreal-engine/blueprint-editor-cheat-sheet-in-unreal-engine
- Basic graph semantics: https://dev.epicgames.com/documentation/unreal-engine/blueprint-foundations
- Blueprint functions and pure/impure: https://dev.epicgames.com/documentation/unreal-engine/functions-in-unreal-engine
- Debugging / watched pins: https://dev.epicgames.com/documentation/unreal-engine/blueprint-debugging-example-in-unreal-engine
- Blueprint compiler: https://dev.epicgames.com/documentation/en-us/unreal-engine/compiler-overview-for-blueprints-visual-scripting-in-unreal-engine
- Graph model: https://dev.epicgames.com/documentation/en-us/unreal-engine/API/Runtime/Engine/UEdGraph
- Node API: https://dev.epicgames.com/documentation/unreal-engine/API/Editor/BlueprintGraph/UK2Node
- Pin API: https://dev.epicgames.com/documentation/en-us/unreal-engine/API/Runtime/Engine/UEdGraphPin
- Graph schema: https://dev.epicgames.com/documentation/en-us/unreal-engine/API/Runtime/Engine/UEdGraphSchema
- Blueprint schema: https://dev.epicgames.com/documentation/unreal-engine/API/Editor/BlueprintGraph/UEdGraphSchema_K2
- UI panel: https://dev.epicgames.com/documentation/unreal-engine/API/Editor/GraphEditor/SGraphPanel
- Pin widget: https://dev.epicgames.com/documentation/en-us/unreal-engine/API/Editor/GraphEditor/SGraphPin
- Wire drawing policy: https://dev.epicgames.com/documentation/unreal-engine/API/Editor/GraphEditor/FConnectionDrawingPolicy
- Action registry: https://dev.epicgames.com/documentation/unreal-engine/API/Editor/BlueprintGraph/FBlueprintActionDatabase

## Decision

**Keep** source-backed semantics, single adapter qualification, immutable graph contracts, dedicated view state, conservative Python analysis, source proposals with preimage checks and undo history, and existing Qt graph renderer. **Modify** interaction eligibility, source wire edits, focused-function usability, feedback, and host acceptance. **Reject for now** graph-as-source-of-truth, a second compiler or AST registry, automatic invented casts/execution paths, alternative scene libraries, and unrestricted visual wiring that cannot be lowered into valid source. The next milestone should demonstrate interaction quality and one complete editable workflow rather than additional node categories.
