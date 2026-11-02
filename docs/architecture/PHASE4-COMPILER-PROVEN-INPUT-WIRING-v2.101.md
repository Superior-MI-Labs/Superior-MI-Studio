# v2.101: Compiler-proven input wiring in source reconciliation

## Existing authority and decision

`SourceDocumentSession` owns text, `ProgramGraph` owns graph IDs, ports and wire edits, `python_lowering` validates compiler semantics. This patch extends the existing `_qualified_source_edit_plan`; it does **not** introduce an AST-to-graph owner.

Option A, rebuilding mutable graph topology from edited Python, would require a new identity model, migration policy, preservation of unsupported source, and risk losing saved graph layout or wires. **Rejected.** Option B, reuse `ProgramGraph.replace_input` for changed operands referencing unique existing generated values, then fully lower a trial graph and compare to edited source, was chosen.

## Contract

1. Only qualified arithmetic and integer-comparison assignment expressions with recognized generated value names are eligible. Source value names must uniquely map to an already generated graph node in the **same function** with a single output pin.
2. The existing input wire is replaced in the trial through `ProgramGraph.replace_input`; its identity and other connections remain intact. Operator and literal edits may be batched. No graph nodes, outputs, or function identities are created from source.
3. Full trial compilation must produce the exact edited generated source (or exact AST in authorized independent-source-trivia mode). Any orphan, changed execution behavior, incompatible ports, unsupported edit or ambiguous mapping refuses all changes.
4. Independent-source review retains source-owned comments, other functions and imports, and requires exact function identity, source revision/digest, disk consistency and graph revision at import. No automatic Python source rewrite.
5. Receipts are advisory. Old/new values identify graph producer and output pin rather than a source byte offset. Original source line/column evidence remains optional and ephemeral.

## Regression and release policy

See `tests/test_v2101_operand_reconciliation.py`: generated/independent sources, combined operation and wiring edits, one atomic import, undo/redo and safe failure on unknown names, orphaned producers and stale owners. Full `scripts/agent-verify.sh --headless`, archive integrity and isolated installation are required. Native Linux Qt still must pass before promotion, cleanup or automatic GUI launch.
