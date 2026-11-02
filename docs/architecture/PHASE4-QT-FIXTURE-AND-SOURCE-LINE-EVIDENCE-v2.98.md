# v2.98 — Qt fixture ownership and independent-source evidence

## Host evidence and actual failure

`qualification-20261102-041636-47889.tar.gz`: doctor passed and native Qt's ProgramGraph subprocess reached independent function review, then `assert len(receipt.changes)==1` failed. The test's own `25 → 31` string substitution made no change because the graph preview held `24`. This was a test expectation failure, not an unsupported compiler edit. A second test defect retained independent-source graph changes into later linked-source tests using the earlier baseline.

## Decision

No fixture may rely on silently substituting a stale literal or expression. Generate independent-source changes from the graph's **current** `preview_python().node_lines` and AST, assert old/new values differ, and require exact-one replacement for the remaining smoke substitutions. Reset shared graph state after the independent source test, including undo/redo qualification; subsequent linked-source tests retain their own source baseline. Two preexisting `assert roundtrip.undo()` expressions were also wrong: `ProgramWorkspace.undo()` is a void GUI command, not the `ProgramGraph.undo()` Boolean operation. The smoke now executes undo then checks the restored graph state. Headless contract tests reject reintroduction. `tests/test_v298_native_reconciliation_fixture.py` replays the history without Qt, so this class of failure is caught even where PyQt6 is unavailable.

## Source review evidence

For each already compiler-proven change, map the graph node to its unique canonical generated assignment target and find that target exactly once within the explicitly selected original function. Report `(function, graph_node_id, source_line)` as read-only `change_lines`; the GUI includes the line when present. Reordered functions, unrelated imports, comments and line shifts remain owned by `SourceDocumentSession`. There is **no persistent line map** or fuzzy match. A selected source function whose parameters, defaults, argument kinds, annotations or return annotation differs from the graph-owned function now fails early with the original source line; the whole compiler remains the acceptance authority. Missing or ambiguous targets yield no location. Import uses the existing immutable source SHA/revision and graph revision plus an entirely new compiler proof before one atomic graph transaction. This adds context without weakening the refusal boundaries.

## Qualification and future work

Focused headless replay, independent-source batches, native smoke-contract checks, full agent headless gate, ZIP manifest and isolated install are required. Native Qt must still run on WolfCat-Studio; the CI native job remains an early warning only. After a host pass, improve precise conflict reporting and stable source-function correspondence only when correctness proofs permit it.
