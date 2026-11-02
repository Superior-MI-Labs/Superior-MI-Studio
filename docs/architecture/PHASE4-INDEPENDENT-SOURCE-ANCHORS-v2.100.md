# v2.100: Static function binding identity and original-source statement spans

## Decision

The sole source authority is `SourceDocumentSession`; the sole executable graph authority is `ProgramGraph`. Their Python adapter `python_lowering.py` already proves graph edits by complete trial lowering. We compared (A) a persistent node-to-source mapping/index and (B) a bounded read-only AST check and ephemeral source-owner evidence. **We chose B.** A second mapping cache or identity database could drift from edited source and falsely authorize edits.

## Changes

1. Source function correspondence remains **explicit, exact and top-level**. A unique named `def` is not sufficient when another module-scope binding also shadows that name. A bounded AST visitor now refuses detected imports/aliases (including wildcard import), assignments, annotations, deletes, classes, definitions, match captures, exception bindings, top-level compound statements and assignment expressions in module-scope comprehensions. It does not descend into function/class/lambda/comprehension local targets. This is a conservative static guard only; dynamic Python `globals()`, `exec()` or monkeypatching cannot be proven equivalent. The unselected remainder of a Python file stays source-owned and opaque.
2. Reconciliation receipts now optionally contain an original source AST assignment **statement span** `(function, graph node, start line, start column, end line, end-exclusive column)`, in Unicode codepoint columns. The corresponding old line-only evidence remains compatible. An index is built once per selected function and only unique target bindings qualify as evidence. Ambiguous locations are omitted rather than guessed. The GUI review displays the source span but does not navigate or overwrite based on it.
3. Import recomputes all evidence from the current session, verifies the SHA and revision of the entire source buffer and graph revision, repeats the compiler proof and makes one undoable transaction or refuses atomically. Unknown Python remains unmodeled; the generated Python adapter is not an arbitrary AST compiler.
4. The release contract checks the README quick-install command against `install_linux.VERSION` and `INSTALL-AND-REPORT.sh`, preventing the stale example script that survived v2.99 documentation. Versioned install folders are sorted by parsed numeric version segments rather than pathname lexicography, so `v2.100` follows `v2.99` and historic cleanup remains deterministic.

## Qualification

`tests/test_v2100_source_region_anchors.py` covers source line/column receipts, reordered selected functions, atomic undo, no-op shadowing refusal, duplicate/static rebinding diagnostics, local-scope exclusions, and stale receipt refusal. `tests/test_v2100_release_consistency.py` verifies release identities. Run the complete headless gate, build via the existing deterministic release builder, verify exact ZIP and isolated headless install. Native Qt PASS on WolfCat-Studio remains mandatory before promotion or cleanup of old managed installations. Previous confirmed baseline: v2.98.
