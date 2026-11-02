# v2.97 — Typed integer comparison qualification

## Goal and ownership

One programming feature across the existing three owners: `ProgramGraph` holds typed operations and undo history, `python_lowering` owns executable Python meaning and source-edit qualification, and `SourceDocumentSession` retains independently authored text. `GraphDescriptor` and Qt remain read-only presentation layers. No new graph model, importer, independent AST cache, or source rewrite.

## Supported changes

The six integer comparison operations `python.less_than` (`<`), `python.equal_int` (`==`), `python.greater_than` (`>`), `python.less_or_equal` (`<=`), `python.greater_or_equal` (`>=`) and `python.not_equal_int` (`!=`) all expose `left:py:int`, `right:py:int` and `result:py:bool`. Existing graph operation menus see them through `NODE_TEMPLATES`. The Python adapter maps each operation to one AST comparison class. The same table drives inverse recognition of source edits. A trial graph is constructed and re-lowered to prove the **entire** candidate, before any real graph transaction. Source text is not rewritten. In independent-source reviews only explicit functions participate; unselected Python remains opaque.

## Refusal boundaries

No chained comparisons, membership/identity checks, implicit casts, dynamic operand rewiring, new statements, moved calls, type widening, arbitrary AST import or renaming by similarity. Unsupported changes reject the whole selected batch without publishing a partial graph. External source conflicts and graph revision changes still refuse. A syntax error in an independent file reports the real source line and column rather than attributing an unparseable file to a graph function.

## Qualification

Focused `test_v297_integer_comparison_family.py` covers all six semantics and canonical ports, source import, branch/nested branch compilation, undo/redo, independent files with opaque source, rejection cases and syntax provenance. `test_v296_comparison_reconciliation.py` retains its compatibility checks, with unsupported variants updated to exclude the newly qualified operators. Full doctor, agent setup, generated Python and ProgramGraph gates remain required; native Qt is independently required for host promotion. No performance or multi-language support claim follows from this addition.
