# v2.74 — Bounded Repeat and loop-carried local state

## Baseline / evidence

v2.73 qualified on WolfCat-Studio in `qualification-20261101-182000-15603.tar.gz` (873 headless tests; native recovery/document/program/integration stages all PASS). v2.74 headless and package results are tracked in the release handoff. Native v2.74 is not qualified until its independent ProgramGraph Qt stage passes on Linux.

## Architectural decision

**Option A — generic mutable CFG and back-edge scheduling. Rejected.** Unrestricted cycles demand SSA/phi handling, state merge, dominance, effects and termination semantics not represented by the existing structured execution validator.

**Option B — Python-specific text template expansion. Rejected.** Would bypass the AST lowerer and graph/source mapping, duplicating semantic authority.

**Option C — bounded Repeat as a structured control node with separate Body and After paths. Implemented.** Keep one `ProgramGraph` document, its canonical node templates, the existing read-only descriptor renderer, `python_lowering` for AST validation and generation, and the existing safe publication boundary.

`python.repeat_int` consumes `exec` and `py:int count`, exposes `body` and `after` execution outputs. The body terminates only in `python.repeat_end`. The count is evaluated at entry exactly once; negative counts and counts > 10,000 raise `ValueError` at runtime. No automatic code execution occurs on graph open, preview or publish. The generated Python `for` is a structured consequence of the graph, not graph geometry. The Repeat node maps to the For line, and Repeat End maps to its body end.

A state slot must be declared before the loop. Its assignments in the body are observed after the loop; each `read` captures a new snapshot at its execution point. Loop-body values and locals are not implicitly available on the After path. Unconnected or invalid graphs persist, but cannot lower or publish.

## Explicit limits

No free-form control backedges, nested loops, Branch within Repeat body, early Return from body, break/continue, effectful graph calls, or arbitrary effect scheduling. A counted loop is one qualified subset, not evidence of a complete Python/Blueprint loop language. Python function parameter types remain statically declared contracts and are not general runtime type enforcement.

## Qualification and rollback

Headless: `python3 -m unittest tests.test_v274_bounded_repeat` and `python3 scripts/program-graph-python-gate.py` plus `./doctor.sh`. Real native: isolated ProgramGraph smoke opens saved loop fixture, previews source, adds/undoes an incomplete node, saves and publishes. Failed qualification must preserve previous installed versions. Roll back by running the previously host-qualified v2.73 package; do not overwrite unknown user graph files.

## Next architecture gates

1. Effectful function calls with explicit execution input/outputs and pure-call boundary.
2. Loop internal Branches, conditional continuation and loop-carried state merges with shape/dominance checks.
3. Source/graph reconciliation and conflicts, then Blueprint node ergonomics and Python IDE tooling.
