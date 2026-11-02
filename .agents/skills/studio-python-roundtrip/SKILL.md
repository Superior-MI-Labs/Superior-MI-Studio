---
name: studio-python-roundtrip
description: Develop or review Python AST-to-graph, graph-to-Python and text/visual synchronization operations with exact source fidelity, effect safety and revision checks. Use for node semantics, pins, calls, branches, returns or code generation.
---

# Python semantics and round-trip contract

1. Read `docs/architecture/DECISIONS-AND-NON-GOALS.md` and `docs/V252-FUNCTION-CALL-AUTHORING-CONTRACT.md`; locate actual source in `python_graph.py`, `python_authoring.py`, `python_edit.py`, `source_connection.py`, `semantic_contract.py`.
2. Identify which artifact owns meaning: live source buffer, future native `ProgramGraph`, or read-only `GraphDescriptor`. Never conflate them.
3. Define input revision, precise operation IDs/pin roles, scope/symbol bindings, control/value edges, effect evaluation order, import/source-map provenance and output artifact.
4. Draft and invalid graph nodes may be saved; code generation and publish are distinct. Qualify complete function+dependencies (not individual visually green nodes). Block a reachable incomplete conditional; don't invent a default branch.
5. Preserve effectful calls (especially reused stored call results), return paths, `and/or` short-circuit, side effects, exceptions, comments, Unicode, CRLF, unknown AST nodes and external file modifications. Source text must not be round-tripped through `ast.unparse()` as a lossless formatter.
6. Use existing validated operations/proposal writer. For new graph-authoritative lowering prove one small complete subset with deterministic node-order-independent output; do not hand a mutable graph directly to Qt for code emission.
7. Build a positive corpus plus adversarial tests: staleness/conflicts, unsupported expressions, partial node, stale undo, import, cross-file symbol, nested scope, duplicate execution, preview vs publish.
8. Run headless suite and Python-first gate, and native Qt when interactions changed. Report supported subset and refusal boundaries precisely.
