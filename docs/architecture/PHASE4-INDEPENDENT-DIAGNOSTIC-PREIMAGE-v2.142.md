# v2.142 — One owner gate for successful and failed independent-source proofs

## Issue

The independent-function planner already checks exact source saved bytes and
graph revisions around successful compiler proof and span evidence. Its
per-region diagnostic fallback, however, re-runs the compiler to identify a
bad function after a failed multi-function review. If the source editor,
saved-byte preimage or filesystem changed **during this diagnostic rerun**,
the previous code still returned a function-specific ProgramGraphError
describing a different revision. Its combined-failure fallback had the same
problem. The UI could misattribute a conflict to code the user no longer has.

## Decision

Reuse the module's existing `_assert_independent_source_snapshot` helper
and ProgramGraph revision check. A small, **lexical** `assert_proof_owners`
guard within the existing `_independent_functions_plan` is now called:

- after full proof failure before attempting a regional attribution;
- after a failed regional proof before naming its source lines;
- after all regional proofs before returning a combined refusal;
- before and after successful line/column evidence mapping.

This replaces duplicated success/failure checks with one consistent gate.
It does not create a persistent proof owner, snapshot cache, new parser,
transaction, or extra compiler pass. Each region still uses the original
`_qualified_source_edit_plan`; no subset is imported on batch failure.

## Regression evidence

`tests/test_v2142_independent_diagnostic_preimage.py` uses the existing
source/graph fixtures. Six tests prove a normal positive import and fail
closed when an editor update, external disk write, saved-byte-only change
or ProgramGraph revision occurs during a failing per-function diagnostic.
It also simulates a combined-only compiler refusal where the separate
region proof succeeds but its live source changes before attribution.

Source-owned files remain untouched by reconciliation. Original diagnostic
behavior remains when owners are stable, while late ownership conflicts
take precedence. GitHub headless/native CI and independent Linux Mint
host qualification remain separate gates.

Rollback to v2.141 if an existing diagnostic pathway regresses.
