# v2.115 — Independent Python source-only local syntax

## Problem

The existing `ProgramGraph` compiler can prove the same operations in independently authored Python, but ordinary, non-executing Python syntax (`local: int = expression`, `pass` inside a populated branch) caused a structural mismatch before the graph equivalence proof. The original author-owned source must not be rewritten or misrepresented as a graph.

## Approaches

A. Extend a generic AST-to-graph importer with new annotation and pass nodes. Rejected: duplicate semantic ownership, new synchronization pathways and unsupported graph nodes.

B. Conservatively normalize only the **ephemeral independent-source proof AST** and then require the unchanged full compiler and atomic transaction gates. Accepted: no graph/schema/source authority changes.

## Contract

- A local annotation is normalized only if it has a simple Name target and annotation in `int`, `bool`, `str`, and a present RHS. No attribute/subscript bindings, complex annotations or annotation-only declarations. The original source remains authoritative.
- Direct function-body `pass` and redundant `pass` within populated `if`/`else` and loop bodies can be ignored in proof; empty suites remain and fail unless otherwise reproducible. Do not normalize unrelated syntactic forms.
- Actual compiler trial, node identities, revision/SHA checks, unsupported edits and one undoable import remain unchanged. Linked generated-source imports retain strict byte/source proof.
- Original-source evidence indexes annotated assignments by their receiving Name. Argument-expression spans are advisory; they never authorize import.

## Qualification

`tests/test_v2115_independent_source_syntax.py`: keyword argument rewiring through annotated local binding, exact original source receipt, undo and unchanged source, nested branch pass, strict linked-source refusal, effectful/complex annotation refusal and empty/changed control suite refusal. Full headless gate and WolfCat-Studio Qt host gate remain required for promotion.
