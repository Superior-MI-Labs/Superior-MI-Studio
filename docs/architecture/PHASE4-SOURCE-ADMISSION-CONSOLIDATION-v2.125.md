# Phase 4: Source admission consolidation (v2.125)

Status: implementation candidate. No new ADR or source authority.

## Observed issue

`_independent_functions_plan` combined graph/source conflict gates, index creation,
explicit selected-name validation, qualification of unselected keyword-call
targets, module-level shadow checks, and compiler transaction authorization.
Those are all legitimate checks, but unrelated source admission details
obscured the final trial compiler boundary.

## Options

- **A:** new reconciliation/index provider serving different language adapters.
  Rejected: duplicates the Python semantic owner, encourages mutable caches,
  adds a second identity source and speculative language interfaces.
- **B:** move the existing pure index and module/keyword admission into
  private, per-review helpers in `python_lowering.py`. Selected. No new state.

## Invariants and proof

The source file and session text are never rewritten by these helpers. A
selected function is named exactly, unqualified/async/duplicate definitions
fail closed, module shadows block selected functions, unsafe callees do not
become permission to rewrite keyword calls, and the original full graph
compiler remains the sole acceptance gate. No partial imports or new Python
syntax. The new tests verify one module shadow traversal for a batch,
several negative cases, and source AST immutability. The existing full headless
suite and CI-native smoke remain mandatory. v2.124 has host PASS; v2.125 is
pending local native qualification.

Rollback: restore the v2.124 versioned archive, not a second install process.
