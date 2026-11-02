# Phase 4 — definition-time source identity and bounded reconciliation (v2.109)

## Problem

The independent Python function reviewer protected selected top-level names
from obvious module assignments, imports and declarations, but its visitor
skipped other definitions entirely. Python evaluates default parameters,
annotations, decorators, class bases and class keywords immediately when the
module defines those objects. Assignment expressions in those positions may
rebind a graph-selected name before the reviewer ever examines the body.
Similarly, an explicit class-body `global` directive can make an assignment
write to the module despite ordinary class attributes being locally owned.

Independent multi-function diagnostic fallback also recompiled every selected
region on batch failure, even when some functions were byte-for-byte unchanged.
Source-evidence projection walked the same owner AST repeatedly for different
statement families.

## Decision

Evolve the current `_module_function_binding_conflicts` AST visitor. Inspect
only expressions evaluated at definition time and explicit class-suite global
writes; do not traverse deferred function/lambda bodies or treat class-local
attributes as module bindings. Retain conservative refusal on explicit shadow
and retain the existing compiler as sole authority for supported edits.

On rejected multi-function batches, use AST equality to skip unchanged region
probes. Keep the full combined trial proof mandatory; changed-region probes are
only refusal diagnostics and cannot authorize an import. Index the existing
compiler-proven read-only source receipt families in one AST pass per owner.

## Rejected alternatives

- Execute source to determine actual runtime binding: unsafe, effectful and
  incompatible with static review.
- Maintain a second mutable symbol table or cross-file source mapping: duplicate
  authority and stale-state risk.
- Accept individually proven functions when the combined graph is refused:
  violates atomicity and can conceal cross-function dependencies.

## Verification and limitations

`tests/test_v2109_module_definition_binding.py` covers module evaluated
rebinding, local/deferred scopes, atomic successful review, and bounded refusal
probes. Existing v2.100 and v2.108 correspondence/source-receipt suites must
remain green. This is not whole-program Python name resolution: dynamic
`exec`, imports with runtime effects, and arbitrary executed callbacks remain
source-owned/unsupported by the graph model.

Native Qt host qualification and safe installation gating remain unchanged.
