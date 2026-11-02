# v2.7 — Definition/Invocation Semantics and Execution Channel Qualification

**Baseline:** v2.6 recovery candidate. **Code scope:** existing Python AST adapter, normalized semantic contract and Qt port presentation. **Delivery:** v2.7 source archive. **No separate graph engine, parser, persistence system, or execution evaluator added.**

## Architectural decision

Approach A: mirror Unreal's white triangles on all source-expression calls, and create separate inner/outer ports. Rejected. Python calls inside expressions have evaluation-order, short-circuit, exceptional and dynamic-dispatch behavior not described by a linear Blueprint-style execution wire. A second port registry would also create a second authority and complicate source edits.

Approach B: retain one canonical validated node/port/edge graph; have each language adapter declare limited semantic role evidence; derive UI affordances from that one descriptor. Accepted and implemented as a bounded step. A call expression may be effectful even when no white triangle is displayed; the UI says effects remain unverified rather than suggesting purity.

## What changed

1. `python_graph.py` emits `semantic_role='definition'` for module functions/classes, nested definitions and class methods, and `semantic_role='invocation'`, `effect_verification='unverified'` for CALL expressions. Existing readable presentation roles (`control_region` and `binding_write`) remain unchanged. A class-method construction path lacking the role was found by tests and updated; no renderer exception was added.
2. `semantic_contract.py` validates those optional roles, rejects ungrounded pure/effectful claims, and provides `port_presentation_role` to distinguish a **definition's result interface**, a **runtime invocation result**, and **definition-time control**. Legacy graphs may leave roles unspecified, without guessed meaning.
3. The same contract now requires a `control` edge to connect output and input `execution` types, and forbids `data`, `call`, `reference`, and `imports` edges from using `execution` endpoints. It preserves opaque cross-language data types, without imposing coercions or assuming syntax/execution semantics.
4. `gui.py` uses the validated descriptor for tooltips and inner boundary aliases. A nested Python `def` has legitimate parent-level control flow for binding the name, but that flow must **not** mirror into the nested implementation body. Its internal ENTRY still represents invocation-time entry and is not wired to definition-time flow. Its return boundary stays a single existing result dot and read-only completion facet.
5. `qt_smoke.py` checks that the outside definition-time exec pins remain visible while their inside aliases are hidden. Folded/early return host smoke remains part of the same existing harness.

## Explicit nonclaims

- v2.7 does **not** make the graph executable, compilable, or a complete Python execution trace.
- A callable reference edge is not evidence that a function was called. A function definition's result interface is not a runtime result.
- Absence of white execution pins on a Python call is not proof that the call is pure; `effect_verification='unverified'` says the opposite.
- Source evaluation order for calls inside boolean operators, chained comparisons, `try/finally`, generators, coroutines and dynamic dispatch is **not** fully modeled; unresolved behavior must remain visible/opaque, not silently linearized.
- The renderer still consumes some legacy dictionaries for geometry. The normalized descriptor now owns role/edge/channel assertions, but complete renderer migration is a future controlled change.
- The host Qt test was updated, but PyQt6 is absent in the build container. **Do not call native rendering qualified until the Linux Mint Qt smoke actually passes.**

## Verification

- 255 inherited tests + 9 new tests = 264 headless unit tests, **passed**.
- The tests cover no-call definitions, call-site results, nested definition-time flow, class methods, unknown effect status, unknown-language typed ports, malformed control/data/call wires, unsupported purity claims, and nonmutation during normalization.
- `./doctor.sh`: Python compilation, headless suite, source graph smoke checks, and icon atlas fallback; see build evidence logs.
- `bash -n` and `unzip -t` used on the package and launch scripts; `test-qt-offscreen.sh` stays a host-only acceptance gate.

## Linux host acceptance

Install as a separate `~/Projects/Superior-MI-Python-Visual-Programming-Lab-v2.7` directory, preserving v2.6. Run:

```bash
cd "$HOME/Projects/Superior-MI-Python-Visual-Programming-Lab-v2.7"
./doctor.sh
./test-qt-offscreen.sh 2>&1 | tee "$HOME/Downloads/SMI-v2.7-Qt.log"
./launch-linux.sh
```

Inspect a nested `def` while its parent is expanded. The outer *flow* and *next* triangles belong to name-binding at definition time. The nested implementation should show its own ENTRY and RETURN, without duplicate inner white triangles implying that defining it runs it. Also inspect `nested_expression` folded RETURN (both value/control endpoint geometry), multiple early returns, camera pan/zoom/resize and source diff review.

## Next step, not included

Before a second language adapter or broad GUI expansion, qualify v2.6/v2.7 Qt interactions on the actual Linux host, then move the remaining graph presentation and interaction capabilities onto the validated descriptor. The next adapter should be a deliberately small read-only producer emitting foreign-language nodes, source provenance, opaque value types, and explicit unknown flow/effects. It must never get a second source-edit authority or assume Python function-call behavior.
