# v2.30: One operation meaning, optional presentation regions

**Status:** Implemented and headless-tested semantic migration step. The legacy inline conditional/loop container **still exists in the Qt renderer** and is not yet the long-term authoring UI. Native Qt qualification is required on Linux Mint. This release does **not** implement drag-to-create operations, generic source emission, language adapters beyond Python, or arbitrary graph rewiring.

## Why we changed it

The same source-backed Python `if` had been called a `control_region` in the readable adapter, and the renderer could embed a child viewport inside its card. That describes presentation as if it were language semantics. Unreal Blueprints instead use a **Branch operation** (condition + True/False execution outputs), with **collapsed graphs** as separate organizational constructs with input/output tunnels. An Unreal function has an **Entry node** (exec output and parameter values), a **Result node** (exec input and returned values), and distinct **call-site nodes**. Changing function inputs and outputs updates both the function graph interface and its calls. Blueprint functions add data input/output parameters, while macros/collapsed graphs may expose more varied execution tunnels. See official references below.

Our target is not to force Python execution into Blueprint semantics. Python evaluation order, exceptions, `for…else`, generators, decorators, and dynamic dispatch must remain adapter-qualified. Impure Blueprint functions have execution pins; a data-only Python call result does not imply the call is pure.

## Two approaches compared

1. **Keep the IF/loop embedded viewport as semantic ownership**, then add a second authoring hierarchy for standalone Branch/Loop nodes. Rejected. This duplicates operation identity and confuses source edits with view organization.
2. **Keep the existing source nodes, ports and edges authoritative**, classify control operations separately from view containment, and progressively migrate Qt to the resulting descriptors. Chosen. No duplicate AST, graph documents, ports, or editable source authority.

## What this version changes

- Readable `IF/ELIF` and loops explicitly declare `semantic_role='control_operation'`. Their normalized descriptor `operation_kind` is `branch` or `loop`, even if the renderer temporarily embeds the body.
- The normalized `NodeDescriptor` now exposes a **definition_graph** only for callable definitions, and **presentation_region** only for control-operation view regions. A graphical child viewport is not a reusable callable implementation.
- `describe_graph()` rejects control operations masquerading as function or organizational interfaces and requires real control successor pins.
- A collapsed conditional/loop retains its validated `graph_interface`, exit channels and unchanged source edges. Earlier code accidentally removed interface metadata when a region was collapsed. This is a core correctness fix.
- `operation_catalog.py` derives a read-only **observed operation inventory** from actual validated source descriptors. It has no independent node definition tables, guessed ports, or authoring permissions.
- The same module derives **function boundary inspection** from definition interfaces, source parameter-binding nodes and actual return sites. It never creates new executable Entry/Result nodes, duplicate return pins or runtime call edges.
- Tests cover unchanged source and edges on collapse, malformed interface refusal, non-invented authoring capabilities, nested/early returns, definition-vs-invocation, and a guarded Python literal edit with a parse/reproject round trip.

## Function/port mapping target

| Concept | Source authority | Visual-authoring target |
| --- | --- | --- |
| Function declaration | Python AST definition and symbol scope | Definition resource/inspectable function graph; declaring it doesn't execute body |
| Function Entry | Function signature and parameter bindings | One projected Entry node: execution starts on invocation; parameters are *outputs* inside function |
| Function Result / Return | Source-backed `return` sites and function interface | Result node: execution *input*, typed returned value *input*. Multiple source returns remain distinct paths |
| Call site | Actual Python `ast.Call` | Separate invocation node with arguments and result; control/effect semantics only when adapter can prove them |
| Branch | Actual `ast.If` | A single control operation, boolean condition, True/False successors; no implicit nested executable graph |
| Loop | Actual `For`, `While`, `AsyncFor` etc. | Loop control operation and source-backed body/else/exception regions; only qualified paths drawn |
| Collapsed Graph | Explicit organizational grouping, not inferred from every `if` | Optional organizational graph with real tunnel interfaces and no new source execution semantics |

**Do not** infer a function call has been executed from a white triangle on the *definition card*. Do not equate returned data with execution completion. Do not turn a Python branch into a macro merely because its operations were visually grouped. Real source text remains authoritative until a validated authoring transaction is approved and saved.

## Next large migration gates

1. **Complete native Qt qualification** of this semantic contract; verify existing return routing and nested graph presentation did not regress.
2. **Migrate control-operation rendering**: `IF/ELIF` and loop cards stay normal compact operations; body/branch membership becomes a separate source-backed control region layer, and only functions, explicit organizational groups and resource contents remain true nested graphs. Keep original source IDs and existing real control/data edges. Preserve old tests as migration evidence and rewrite assertions about former *UI nesting* accordingly.
3. **Unify function Entry/Result presentation**: one source-backed definition interface drives the internal Entry/Result projections and external call-site signature. Validate early returns, no-return, nested functions, control flow, purity/effects, and type annotations before drawing any new execution relationship.
4. **Adapter-advertised authoring operations**: add an actual capability contract to the existing adapter, not a separate library definition authority. Only advertise creation/edit/source-emission actions when a specific guarded transformation exists and round-trip tests qualify it. Prototype a Python branch insertion without claiming arbitrary Python synthesis.
5. **Bidirectional workflow and language adapters**: round-trip source → graph → proposed source → reparse and compare stable semantics, then qualify a second read-only adapter and grow operations by proven language-specific capability.

## Qualification discipline

- Headless doctor + regression suite, exact ZIP fresh-extraction doctor, static shell syntax, ZIP integrity and isolated installer rehearsal. The installer also restores executable shell-script bits from the validated archive without trusting arbitrary file modes.
- Host `RUN-ALL.sh` Qt smoke and screenshots for graph layout, early returns, collapses, tabs, minimap, dock regions, and selected camera panning.
- Unsupported graph rewiring and visual programming remain explicitly refused. Do not mark those capabilities implemented because the observed catalog exists.

Official documentation, accessed October 2026:
- [Blueprint Functions](https://dev.epicgames.com/documentation/unreal-engine/functions-in-unreal-engine)
- [Blueprint Flow Control](https://dev.epicgames.com/documentation/unreal-engine/flow-control-in-unreal-engine)
- [Blueprint Graphs](https://dev.epicgames.com/documentation/unreal-engine/graphs-in-unreal-engine)
- [Collapsing Graphs](https://dev.epicgames.com/documentation/en-us/unreal-engine/collapsing-graphs-in-unreal-engine)
- [Blueprint Nodes / tunnels](https://dev.epicgames.com/documentation/unreal-engine/nodes-in-unreal-engine)
