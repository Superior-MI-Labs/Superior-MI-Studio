# v2.114 — Independent Python local-name correspondence

## Problem and options

`SourceDocumentSession` preserves user source and `ProgramGraph` owns qualified visual semantics. Prior reverse import assumed every generated temporary retained its compiler spelling, making an ordinary source-only rename a conflict. A separate editable symbol table or AST importer would duplicate ownership and require unsafe synchronization.

**Chosen approach:** transient alpha-normalization of a copied, explicitly selected source function before the existing full trial graph lowering. No new graph nodes, source buffer edits, persistent aliases, or runtime code execution. Direct-body `pass` and a leading function docstring remain source-owned; compiler proof excludes them only in the temporary candidate.

## Qualification boundaries

- Original assignment and selected source assignment must correspond by position with the same one-target structure. Rename only a unique compiler-generated `_smi_value_N` to a unique ordinary local, and only if absent from parameter, canonical generated symbol, or function-call target identities. Reordered, repeated, moved, ambiguous, nested-scope, or global/nonlocal cases are refused, not guessed.
- The underlying Python function signature remains unchanged. Keyword argument conversion from v2.113 still runs on the same candidate. The existing whole-graph compiler and atomic edit transaction remain final authorities; review and commit both recheck revisions.
- Original source, whitespace, comments, docstring and `pass` stay byte-identical. Graph publication deliberately does not reproduce source-owned docstring reflection metadata. This is partial representability, not general AST import.
- Generated-source import remains strict and does not receive these normalizations.

## Qualification

`tests/test_v2114_independent_local_correspondence.py` covers accepted aliases with actual call rewiring, docstring/pass preservation, multi-function isolation, collisions/duplicate targets, scope changes, and external revision conflict. The complete headless release and separate native Qt host gates remain required.
