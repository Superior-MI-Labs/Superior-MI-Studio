# Phase 4 — v2.106 execution-owned value inputs

## Architecture decision

**Reuse the existing compiler/ProgramGraph transaction rather than adding a source-to-control-flow importer.**

Alternative A would parse edited Python into a second mutable graph or infer new execution nodes and then reconcile identities. It would duplicate the source authority, permit lossy migrations, and make effects and loop evaluation order ambiguous. Rejected.

Alternative B extends `python_lowering._qualified_source_edit_plan` with source-operand shapes for already-owned Bind, Local declaration, Local assignment and Repeat count inputs, then applies only `ProgramGraph.replace_input` commands to existing typed ports. The complete compiler trial must reproduce the exact generated source (or the qualified independent-function AST) before any atomic import. Accepted.

## Repeat-specific proof

A Repeat node maps to its `for` source location, while the count is evaluated exactly once into a generated `_smi_repeat_count_N` assignment, followed by a range guard and structured body. Qualify the existing `range(_smi_repeat_count_N)` loop and its unique earlier count assignment in the current function. Only that assignment's RHS may select an existing same-function producer. The compiler trial rejects direct constants, unknown producers, moved statements, modified guards, renamed indices, altered effects, and orphaned nodes. No special separate count owner is created.

## Source receipts and safety

Independent authored source stays authoritative and unchanged. Read-only receipts report exact RHS AST spans, including repeated generated mutable slot targets. Ambiguity or differing assignment counts omits optional position evidence; it never authorizes a commit. Reviews do not mutate the graph. Imports recheck exact current source/graph revisions and digest and use the graph owner's single undoable transaction.

## Qualification

Run `tests/test_v2106_state_and_repeat_reconciliation.py`, the preceding control/ordered-call and state/Repeat tests, `bash scripts/agent-verify.sh --headless`, package integrity and isolated install. Native Qt on WolfCat-Studio is required to promote v2.106. Avoid promising universal Python import or arbitrary control-flow rewrites.
