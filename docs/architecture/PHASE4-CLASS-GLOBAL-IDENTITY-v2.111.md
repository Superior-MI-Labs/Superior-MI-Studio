# ADR — v2.111 class-global function identity

**Decision:** extend the existing AST-only module binding guard, not a second
importer, and transiently index source and graph baseline function definitions
per batch. No project code is executed.

## Problem

Class bodies can explicitly declare `global name` and bind that name with
imports, function/class declarations, exception aliases, pattern captures, or
normal writes. The earlier guard tracked only AST Store/Del nodes and missed
several non-Name bindings. A nested class also has its own class-local name
scope, but its explicit global writes still affect the module.

## Contract

- Only explicit `global` writes originating in a class suite are treated as
  module-level shadows of selected functions.
- Class locals, nested class names, comprehension iteration targets and
  deferred method/lambda bodies are not module shadows by themselves.
- Decorators, bases, defaults and annotations are evaluated at definition time
  and examined in their correct enclosing scope.
- The index of exact source and canonical function names is temporary and
  cannot be used for fuzzy function matching or to authorize edits.
- Review remains read-only. Every import revalidates file revision/digest,
  graph revision, full compiler proof and one atomic transaction.

## Alternatives rejected

- Running external Python to resolve identities: violates the non-executing
  compiler boundary and may cause arbitrary side effects.
- A persistent function-name cache or new source-owner model: creates a second
  source of truth and more invalidation paths.
- Treating all class-local definitions as module shadows: rejects legitimate
  independent Python source without evidence.

## Acceptance

`tests/test_v2111_function_scope_identity.py`, v2.109/v2.110 identity suites,
full headless release gate, and native Linux Qt qualification before promotion.
