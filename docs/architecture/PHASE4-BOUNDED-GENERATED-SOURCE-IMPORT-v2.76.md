# Phase 4: Exact generated-source import proof, v2.76

**Status:** headless source-only proof, not interactive bidirectional IDE support.

## Owner and scope

The existing Python lowering adapter owns generated-source qualification; `ProgramGraph` remains the only writable graph authority. No new parser, source file writer, reconciliation database, language adapter, Qt framework or runtime was introduced.

A user-created draft of graph-generated Python can be presented for *explicit* import with `(expected_graph_revision, base_source, edited_source)`. A strict, temporary AST scan identifies exactly **one** source-map-backed primitive literal assignment or compatible arithmetic operation change. A candidate graph is edited in isolation and entirely re-lowered. Only when its newly generated source **exactly equals** the supplied edited source does one undoable edit commit to the original ProgramGraph.

- Allowed in the first proof: int->int and bool->bool literals; `python.add`, `python.subtract`, `python.multiply` with identical port signatures.
- Refused: other source edits; source formatting/comments; missing or changed base; malformed syntax; multiple edits; mismatched or dynamic ports; stale graph revision; type changes; unqualified source.
- No accidental side effects: Python is parsed and compiled by existing preview only, never executed by the import; no source or graph file is saved automatically. Caller must preserve the edited text outside this API on refusal.
- Existing `set_property` and new *structurally compatible* `replace_node_operation` commands retain all stable node/port/edge IDs and layout positions; the graph compiler independently re-qualifies their semantics. Undo/redo uses existing transaction history.

## Alternatives

1. Reconstruct an entire graph by parsing edited Python or trusting AST-node line numbers: **rejected**; loses identities and unsupported Python.
2. Add a separate graph editing/sync registry: **rejected**; duplicates ProgramGraph ownership.
3. Use existing graph commands and exact compiler round-trip proof with versioned base: **chosen**, until a larger reconciliation service is justified by a complete UI-level exercise.

## Acceptance and next gates

Focused: `python3 -m unittest discover -s tests -p 'test_v276*.py' -v` plus existing `test_v26*`/`test_v27*` compiler tests as needed. Full release: `bash scripts/agent-verify.sh --headless`; host Qt after any GUI integration. Native text editor, source-map spans, three-way conflict UI, comments and arbitrary Python import remain **unimplemented**. Do not mark E4 complete until source and graph editing can both be demonstrated in one real IDE session without data loss.
