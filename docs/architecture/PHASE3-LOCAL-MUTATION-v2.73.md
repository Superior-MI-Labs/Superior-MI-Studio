# v2.73: Explicit execution-local state (Python only)

## Why this is a separate semantic step

`python.bind_*` captures a single immutable value. Turning it into a hidden
mutable variable would make existing data pins time-dependent. Instead, retain
those immutable captures and introduce three explicit operations per type:
`local_*` (declare + initialize), `assign_*` (reassign), and `read_*` (capture
an immutable snapshot at the current execution point).

One document owner, one operation template catalog (`program_graph.py`), and
one AST lowering pipeline (`python_lowering.py`). No interpreter or extra
registry. The source-mapping contract now disambiguates assignments to the
same generated Python name in statement order.

## Exact rules

- A local slot is identified by its declaring node's stable ID. An Assign/Read
  references that ID with `local_id`. Storage uses an internal generated name;
  document names cannot collide with Python parameter names.
- Declaration and assignment require exact `py:int` or `py:bool` values.
  Python's `bool` subclass relationship does **not** authorize integer input.
- Read snapshots occur only on explicit execution edges, after declaration.
  Earlier snapshots do not change when the slot is reassigned.
- Branch paths have independent static slot environments. No join/loop may
  invent a dominating value. Orphan operations and unqualified effects refuse
  Python generation; an incomplete graph remains a valid saved document.
- Pure function calls may not target effectful functions. Publication still
  requires a saved graph and the existing guarded source writer; never execute
  generated code during preview, save or publication.

## Considered alternatives

1. **Reuse `bind_*` as a mutable global name:** rejected; time-dependent data
   output and hidden speculative hoisting would violate the current contract.
2. **Separate mutable state engine / AST interpreter:** rejected; duplicate
   semantics and complicated undo, qualification, and source publication.
3. **Execution-local slots with explicit snapshot reads:** implemented. Fits
   the established structured control tree and makes each mutation observable.

## Proof and limits

`tests/test_v273_mutable_local_state.py`, `examples/qualified-mutable-locals.smi-graph`,
`program-graph-python-gate.py`, and the isolated native ProgramGraph stage
cover typing, precedence, wrong branches, durable persistence, source mapping,
undo/redo and guarded publication. Native GUI acceptance requires host evidence.

**Deferred:** loop-carried state, control joins, dynamic variables and effects,
stateful graph calls, arbitrary Python-to-graph roundtripping, language adapters,
full Blueprint UX and complete IDE tooling.
