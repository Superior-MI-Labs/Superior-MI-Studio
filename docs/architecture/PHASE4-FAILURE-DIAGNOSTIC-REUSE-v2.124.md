# Phase 4: normalized-candidate diagnostic reuse (v2.124)

## Scope and authority

The only implementation change is inside `python_lowering._independent_functions_plan`
for the **failed** all-or-nothing independent-source batch path.
`ProgramGraph` remains authoritative for executable edits;
`SourceDocumentSession` owns text; one whole-graph Python compiler proves
changes. The original AST remains untouched and provides source line spans.

## Alternatives considered

- **New diagnostic owner / secondary analysis:** rejected, because it would
  duplicate compiler semantics and create another source of truth.
- **Reusing the normalized ephemeral candidate and existing graph index:**
  chosen. Failed-batch retries now inspect only normalized functions that
  genuinely differ from the generated baseline. Unselected and proof-identical
  functions cannot independently explain the refusal.

## Integrity and qualification

There is no new supported Python syntax, graph command, source modification,
new import path or UI state. The complete compiler still decides acceptance;
the retry path **never commits** an individually valid region of a failed batch.
Existing bounded 32-function selection applies, and no extra data structure
is stored beyond the synchronous preflight.

`tests/test_v2124_independent_diagnostic_efficiency.py` characterizes
source-only trivia, normalized keyword calls and a genuinely changed producer,
using explicit compiler-call counts plus non-mutation assertions. Full headless
verification and GitHub CI remain release gates; Linux Mint native-host
qualification is separate evidence.
