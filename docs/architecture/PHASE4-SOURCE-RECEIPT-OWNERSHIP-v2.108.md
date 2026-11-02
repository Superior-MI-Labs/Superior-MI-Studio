# Phase 4: function-scoped source evidence, v2.108

## Decision

Independent Python source receipts remain an ephemeral read-only projection
from the already-approved graph/compiler proof. `SourceDocumentSession` is
still authoritative for text; `ProgramGraph` owns graph transactions. There
must not be a persistent or independently editable mapping.

## Root cause and repair

`_independent_change_lines` built `occurrences` separately for every selected
function but later inspected the loop-local variable from only the final
function when emitting evidence for all changes. This could suppress source
locations for prior functions with repeat writes. Keep counts in the per-
function index and require exact target+occurrence identities.

## Presentation semantics

The Inspector should point to the smallest AST node that can be identified
without guesses: the changed input operand/condition/call argument/Return
value, or the RHS of a literal/operator edit. The AST does not expose a safe
standalone location for arithmetic operator tokens, so highlight the full
operator expression. Source columns are converted from AST UTF-8 bytes to
1-based Unicode character positions. If identity is ambiguous, omit the
source span, not the compiler-proven edit.

## Alternatives rejected

- An independent persistent graph-to-source line database: risks divergence
  on unsaved text, undo, reordered functions and edits from other tools.
- Inferring a span from similar syntax, node order or a guessed filename:
  risks directing users to unrelated code.

## Gates

`tests/test_v2108_source_receipt_ownership.py` plus prior source evidence,
compiler round-trip, publication, source session and native Qt gates. This
change does not relax compiler acceptance or source/graph revision checks.
