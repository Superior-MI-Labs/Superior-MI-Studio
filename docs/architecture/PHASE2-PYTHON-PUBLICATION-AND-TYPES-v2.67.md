# v2.67 — Qualified Python publication, type discipline, and graph ownership

## Baseline

`qualification-20261030-233734-129501.tar.gz` for v2.66 shows 788 headless tests and all four independent Qt test stages passed. **v2.67 is a new candidate requiring fresh native Qt qualification.**

## Design decision

Graph-owned `.smi-graph` state remains authoritative in `ProgramGraph`. The Python AST lowering in `python_lowering.py` owns qualification, source maps and publication requests. Existing `python_edit.py` owns all guarded source-file mutation, including exclusive creation. Native `ProgramWorkspace` only invokes these owners. Source-owned `.py` files are separate documents, not implicit live mirrors of graph state.

The two assessed publication alternatives were (A) let Qt write `preview.source` directly and re-use it as a live source mirror, and (B) publish only after exact graph revision checks using the established source writer and an explicit new-file or matching preimage contract. **B is implemented.** A would duplicate mutable document authority and permit silent overwrite. Missing graph file, dirty graph, external modifications, incomplete graphs, unsupported operations, existing files, symlink outputs and unexpected source digests are refusal paths.

`publish_python(graph,path,expected_revision=...)` returns a receipt with SHA-256 of source and saved graph, graph revision, and node-to-source line mapping. The output is an independent `.py` artifact, **not an executable command**. New Python files use private temporary writes, fsync and atomic exclusive hard-link under the existing per-file advisory source lock. Intentional existing-file replacement requires `expected_target_sha256` and goes through the existing `apply_proposal()` preimage, backup and atomic commit. Non-cooperating external writers remain a known advisory-lock limitation.

## Qualified additions

Graph-owned pure `python.subtract` and `python.less_than` are supported alongside v2.66's Literal, Parameter, Add, Multiply, Return and direct nonrecursive calls. The lowering now tracks inferred value types for each node. Input ports must agree with the qualified contract, even when `py:unknown` is persisted as a draft placeholder. `int` and `bool` are distinct: Boolean literals, comparison results, parameters, Returns and direct function calls may be `py:bool`; they may **not** flow into integer arithmetic. Graph serialization and typed undo preserve this distinction.

All node operations are still pure, and the compiler still refuses any control/exec edge. Comparing integers is *not* a runtime Branch; real conditional execution needs an effect-aware control-flow model, verified on a separate gate. No arbitrary assignment, exceptions, I/O, import or graph runtime is implied.

## Verification and limitations

Headless: publish new, exact existing-source digest and backup, concurrent publishers, stale graph revision, dirty graph, externally changed saved graph, missing inputs, symlink destinations, type errors, deterministic source mapping and CLI refusal. The existing `scripts/program-graph-python-gate.py` checks actual publication into a temporary directory with no executable side effects. Native Qt: `QT_STAGE program-python-publication` checks real ProgramWorkspace invocation and source artifact persistence.

**Not implemented:** bidirectional source-to-graph reconciliation, effectful Branch/Loop execution, general local variable mutation, debugging, multi-language adapters, or guaranteed isolation from third-party writers that bypass advisory locks. These remain in `docs/agents/NEXT-TASKS.md` and must not be described as shipped.
