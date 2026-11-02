# v2.116 — Ordered independent Python and local graph identity

## Problem

The independent-source parser already supports readable aliases of uniquely assigned `_smi_value_N` values, and the compiler separately permits pure dependency reordering within a function/branch. The alias pass matched assignments only by position, so composing these otherwise qualified changes failed when their positions moved.

## Approaches considered

1. **Persistent source-to-graph name table**: would become a second authority, vulnerable to stale source revisions and edits, and would need a migration contract for existing graphs. Rejected.
2. **Transient unique-missing/unique-new matching**: identify exactly one disappeared compiler-generated assignment name and exactly one introduced author name from a fresh, same-function AST; require unique assignment, no collision/unsafe nested scopes, and the existing full compiler trial. Adopted.

The existing positional handling for multiple aliases remains conservative, only if unchanged compiler-generated names retain their relative order; no arbitrary anonymous permutation inference. Original source text, annotations, comments and no-op trivia remain authoritative in `SourceDocumentSession`. Graph edits remain compiler-proven, one undoable transaction, and generated-source import remains exact.

## Verification

`tests/test_v2116_structural_local_identity.py` covers top-level/branch reordering, annotated locals, source-only `pass`, source preservation, undo, an external source edit, alias collisions and unsupported statements. Full headless and Linux native Qt gates are still required.
