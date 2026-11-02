# v2.39 — Reference stored Call results, never duplicate evaluation

## Host baseline

The uploaded `qualification-20261029-172034-252624.tar.gz` passed 489/489 headless tests and contains `NATIVE_QT_SMOKE_PASS`. This is the v2.38 host-qualified baseline.

## What changed

- `studio_native/python_edit.py`: a selected CALL result can be used as a connection source only when the exact AST call is the **direct initializer** of a unique, simple local assignment in the same function. The source adapter resolves the corresponding validated SET binding. The emitted source edit references the existing local, never copies a CALL expression or invokes it again.
- The existing straight-line dominance gate proves the producer precedes the consumer within the same lexical arm, and rejects mutation/effect barriers and rebinding. It also rejects nested or effectful evaluation contexts where a prior argument might alter the binding before it is consumed.
- `studio_native/source_connection.py`: the one existing preflight now explicitly distinguishes `stored-reference`, `name-reference`, and `expression-copy`. The Qt hover feedback automatically shows this outcome, so users are not misled into thinking a copied constant expression is a live wire.
- `studio_native/qt_smoke.py` and `RUN-ALL.sh`: add a real Qt drag/hover preflight for Call → consumer, prove source is unchanged, and capture `stored-call-connection.png` on host.
- `tests/test_v239_stored_call_result_connections.py`: 13 regressions covering single invocation, exact Call→SET→consumer reparsed graph edges, named keyword inputs, empty source, cross-arm refusal, mutation/effect barriers, nested calls, prior effectful call arguments, external modification, and UTF-8/CRLF handling.
- `examples/python-v16-stored-call-result.py`: simple manual demonstration.

## What this is not

This does not introduce SSA, general dependency scheduling, type proof, arbitrary Call result cloning, or effects analysis. It creates a **real Python reference to an existing value**, which reparses into a source-derived data path. Python's callable may still be dynamically dispatched; only evaluation **count and source position** are preserved under the explicitly qualified transformation. For a CALL without a stored local, we deliberately refuse instead of inventing a variable or repeating the effect.

Function boundary semantics, Branch and Loop contracts, filesystem/source tab navigation, minimap ownership, and existing atomic source-edit/review tools are unchanged.

## Qualification

- Headless doctor: 502/502 PASS.
- Archive integrity, fresh extracted doctor and isolated headless installer rehearsal: recorded at packaging.
- Native Qt of v2.39: **pending host report**; do not call this patch natively qualified before `RUN-ALL.sh` passes on WolfCat-Studio.

## Patch plan (next stages)

1. Extend explicit data-dependency proof to read-only straight-line values with stable bindings, while requiring actual graph-edge round trips and conservative effect barriers.
2. Unify function Entry/Result and call-site parameter editing, including signature changes and all call-site rewrite safeguards.
3. Migrate remaining global Qt source/document aliases behind per-tab `GraphViewSession`, keeping the one graph renderer and one Python AST authority.
4. Add validated node creation/connection gestures that offer only adapter-proven transformations; identify runtime type uncertainty separately from syntactic qualification.
5. Qualify a second read-only language adapter only after the Python source ↔ graph ↔ source invariants remain stable.
