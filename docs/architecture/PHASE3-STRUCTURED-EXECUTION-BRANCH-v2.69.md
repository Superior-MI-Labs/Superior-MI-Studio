# v2.69 — Bounded structured execution Branch

## Architecture decision

**Owner:** `python_lowering.py` remains the one Python graph-to-source compiler.
`ProgramGraph` owns nodes/ports/edges, even incomplete ones; `GraphDescriptor`
and the existing Qt canvas remain read-only projections. No new interpreter,
CFG subsystem, source writer, or generic operation registry was introduced.

**Rejected A: treat eager Select as a Branch.** It evaluates both producer
arms and has no execution semantics; presenting that as control flow is false.

**Rejected B: implement a generalized arbitrary-flow compiler now.** Loops,
state mutation, implicit control joins, exception paths and effects still lack
qualified rules. A general CFG today would require an unproven second semantic
system or unsafe assumptions.

**Selected C: extend the existing AST lowerer with a narrow structured Branch.**
An Entry has one `then: execution` output; a Branch has `exec: execution` and
`condition: py:bool` inputs and `true/false: execution` outputs; each Return Flow
has `exec: execution` and a value input matching the function return type.
Exactly three control edges are required:
Entry.then→Branch.exec; Branch.true→ReturnFlow.exec; Branch.false→a distinct
ReturnFlow.exec. No extra or disconnected execution nodes are qualified.

The compiler checks *all* reachable nodes and all required data dependencies;
no side-effectful, unknown, orphan or incompatible operation is dropped to
obtain a valid result. It computes the condition's pure dependencies before
`if`; non-condition dependencies are emitted only on their chosen branch. A
producer shared by both return arms is separately bound in each exclusive
branch. Graph geometry does not influence execution order.

## Limits

Only pure integer/Boolean expressions and statically qualified calls into
other pure graph functions are allowed in the structured branch. Neither an
arbitrary Branch continuation nor multiple Branch nodes/loops are supported.
Graph documents can store those unfinished structures; Python preview and
publication refuse them. Generated source is not run by preview/publication.
The runtime does not enforce input annotations, which remains an explicit
Python-lowering qualification limitation.

## Evidence

- `tests/test_v269_structured_branch.py`: behavior, line identity, guarded
  publication, both return types, branching callee calls, shared producer
  placement, geometry independence, incomplete graph persistence, wrong control
  relation, orphan nodes, unexpected signatures, atomic undo/redo and refusal.
- `examples/qualified-structured-branch.smi-graph` and
  `scripts/program-graph-python-gate.py` perform an on-disk preview and
  explicit guarded publication without executing generated Python.
- Native `exercise_program_workspace` checks creation, control connection
  relation, incomplete preview refusal and saved/reopened graph on Linux Qt.
- **Host evidence:** pending. Headless gates cannot certify Qt interactions.

## Next

Establish clear effect classification, explicit variable writes, dominance and
control join rules *before* adding loops or arbitrary Branch graphs. Keep all
second-language work deferred. Later source import/reconciliation must require
exact source/graph revision evidence and preserve unsupported Python.
