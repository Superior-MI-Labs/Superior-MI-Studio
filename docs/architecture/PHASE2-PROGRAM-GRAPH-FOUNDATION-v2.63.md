# v2.63 — Native ProgramGraph v1: owned incomplete documents

**Evidence stage:** independent headless and archive tests. The existing v2.62 runtime is host-qualified in `qualification-20261030-224411-127652.tar.gz`; native v2.63 Qt remains unqualified. No new GUI route or Python compiler was delivered in this patch.

## Decision and alternatives

The existing `studio_native/model.py` owns **presentation-only** `smi.dynamic-node-lab` prototypes. `python_graph.py` owns the **read-only** projection of source-owned Python. They cannot simultaneously own an editable executable program document.

1. **Reuse legacy prototype graph as semantic authority:** rejected. Prototype controls, unqualified types, and UI-only defaults would become executable by accident; legacy file compatibility would drift.
2. **Make the Qt `GraphDescriptor` mutable:** rejected. This duplicates state and makes a renderer/viewport responsible for programming semantics.
3. **Introduce a separate native document authority `program_graph.py`, project it into the existing descriptor:** chosen. A graph-owned program has its own format and revision history, while source-owned `.py` and prototype drafts remain unchanged.

## Implemented in this integrated patch

- Format `smi.program-graph` version 1; one owner for functions, parameters, node operation IDs/versions, data/execution ports, typed edges, annotations, and **separate presentation layout**. Unknown operations and their properties are retained without claiming meaning or executing code.
- Structural checks: exact schema and version, size bounds, stable identities, port/edge endpoints and direction, function-local connections, data versus control lanes, single-writer input pins, safe coordinates, JSON exact round-trip, rejection of duplicate object keys, and failure on invalid external files. Missing required inputs and mismatched *data* types remain **nonfatal semantic diagnostics**, not broken saved documents.
- One revision-aware command owner: add/remove function, parameters, add/remove/move node, set opaque property, connect/reconnect/disconnect, annotate; guarded and bounded in-session undo/redo. Stale revision and invalid edits leave the original state unchanged.
- Persistence: canonical deterministic UTF-8 JSON, exact prior-disk-content check while holding a per-document cooperating-process lock, private temporary write + fsync + atomic replace, bounded `.smi-previous` last-good snapshot. Unsaved state is retained on conflict. The lock remains advisory; third-party editors ignoring it are not made atomic by this design.
- New explicit `GraphDescriptor(origin='program')` projection via the existing `describe_graph`. Nodes/edges are copied into ephemeral renderer payloads; descriptor snapshots are read-only. The native document itself is never stored in that projection.
- `examples/incomplete-program.smi-graph` exercises Function + Add + Return and a disconnected Multiply. The example is intentionally **not compilable**.

## Acceptance and limits

The v2.63 tests cover round-trip, revision monotonicity, editing, undo, stale edits, malformed input, Unicode payloads, cross-function edge refusal, typed diagnostics, concurrent writers, last-good backup, source-execution refusal, and legacy prototype compatibility. They run with no PyQt6 dependency.

**Not delivered / not claimed:** graph-owned tab routing, Qt node placement UX, an operation registry with proven Python semantics, Python lowering/source maps, executable behavior, source↔graph reconciliation, arbitrary multi-language adapters, or full crash/backup recovery UI. A future unsupported document version is refused, **not silently coerced or downgraded**. Stable graph schema decisions may still be revised while format v1 is a headless experiment; any incompatible change must use an explicit version migration.

## Next full acceptance gate

Integrate this **existing** document owner through `graph_routes.py`, `navigation.py`, the established tab/session lifecycle and shared graph canvas. In one native host test: create Function + Add + Return + disconnected Multiply, wire and rewire an input, move a node, undo, save `.smi-graph`, close and reopen it, verify exact IDs and independent camera state. Source-owned Python and legacy `model.py` must remain intact, and no editor action should execute Python implicitly.

After successful native UI qualification, add an *adapter-owned* qualified Python operation vocabulary and smallest whole-function lowering proof. Do not generate source merely by sorting nodes or reading their coordinates.
