# v2.107 — compiler refusal diagnostics and reconciliation cleanup

## Purpose

When independently authored Python differs from the compiler-owned ProgramGraph
representation, users need evidence for **why** an edit was refused. A generic
"changed unsupported syntax" message is safe but sends developers hunting.
The new implementation does not attempt to increase the admitted Python AST
subset or invent an additional AST-to-graph importer.

## Architecture decision

- `SourceDocumentSession` owns current Python text/revisions and disk checks.
- `ProgramGraph` continues to own all executable visual nodes, connections and
  one-transaction undo/redo.
- `python_lowering._qualified_source_edit_plan` retains its exact same
  acceptance rules and whole-program trial re-lowering proof.
- `_source_ast_mismatch` traverses two already parsed ASTs **only on refusal**.
  It returns a bounded first structural disagreement and never authorizes
  source changes. It neither caches AST owners nor persists identity maps.
- Independent-source previews use `ast.unparse` of selected source-owned
  functions inside a synthetic canonical module. Candidate AST line numbers
  refer to that normalized module, **not** the user's original file. Existing
  selected-function source line ranges are the authoritative source location.
- Canonical generated Python is parsed once per preflight for mapper and
  evidence operations; no semantics or source write behavior change.

## Rejection and acceptance gates

Refuse invalid syntax with candidate syntax line/column; reject changed
statements, unknown producer names, altered Return expressions and unqualified
execution effects. Report a first AST disagreement where its trees exist.
A mismatch explanation alone never relaxes graph validation or revision/SHA
checks. Successfully qualified operator/wire edits remain atomic, source-safe,
and undoable.

## Qualification

`tests/test_v2107_reconciliation_diagnostics.py` exercises deep/large AST
bounds, added statements, changed control syntax, unknown names, syntax errors,
source immutability and a valid operator import/undo. Run the existing full
headless gate, archive validation, isolated installation, and the required
Linux/Qt host promotion gate.
