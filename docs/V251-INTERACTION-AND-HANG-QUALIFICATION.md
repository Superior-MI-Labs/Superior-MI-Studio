# v2.51 — Source-backed input editing and supervised native Qt qualification

## Failure evidence and diagnosis

The user's v2.49 and v2.50 installer runs were interrupted while `RUN-ALL.sh` was executing its native offscreen Qt smoke. The user did not provide a v2.50 `qt.log`, so the exact stage of its second hang remains **unverified**. The earlier v2.50 repair fixed a missing `QDialog` import, but inspection confirms that six modal smoke interactions still relied on independent `QTimer.singleShot()` callbacks with no reliable visible-dialog discovery or synchronous callback error propagation. A callback firing without its target modal visible, or failing during automation, could leave an inner `exec()` waiting. This is an architectural fragility of the *test harness*, not proof that the ordinary IDE hangs in normal use.

## Decisions

1. **REJECT** increasing the timeout, suppressing assertions, blindly accepting all active dialogs, or calling this a GUI PASS without Linux host evidence.
2. **KEEP** the Qt smoke as an end-to-end GUI interaction test, but consolidate its six modal cases through `exercise_modal()` in `qt_smoke.py`. It polls the *visible* expected dialog, executes the case-specific assertions, rejects the modal on case failure, then raises the captured failure after `exec()` unwinds. No longer leave one-shot auto-dismissal timers scattered throughout the 1,700-line test.
3. **KEEP** one external process watchdog in `RUN-ALL.sh` (default `SMI_QT_SMOKE_TIMEOUT=90`, configurable), because no in-process timer can rescue a blocked GUI thread. Print `QT_STAGE` markers live through a `tee | awk` pipeline, preserve full `qt.log`, propagate the **actual** child status with `PIPESTATUS[0]`, retain the report and refuse installation promotion on timeout/failure. This is a last resort, not a substitute for fixing the modal lifetime.
4. **KEEP** `python_edit.py` as the AST/source transaction authority. Extract target operand port resolution from existing `rewire_source_operand()` into `_qualified_source_input()` and reuse it for `replace_source_input_literal()`. This avoids a second parser/registry and ensures both drag-to-connect and direct input editing validate current scope, actual graph ports and AST spans.

## Usable new visual interaction

On a Python source graph, double-click an existing input pin. A simple Name read or primitive input may be replaced with a primitive literal through the existing source diff review and guarded transaction. If the input was a visual name connection, this supplies a real source-level replacement rather than leaving an illegal dangling Python expression. Complex inputs (calls, arithmetic expressions and unknown effects), flow pins, stale/incorrect target identities, nonprimitive values and unsafe scopes are rejected. The prior special-case literal double-click remains available. Session undo/redo works because both edits share the existing `SourceEditHistory`.

This is a **bounded Python-only vertical slice**, not arbitrary wire deletion, node deletion, structural control-flow rewriting, or another language adapter. Those will require explicit source and effects semantics.

## Qualification

- 617 headless tests and the Python-first gate: run on this source in the sandbox; see release evidence, do not infer host GUI success.
- Existing Qt smoke now exercises the source input replacement proposal; six modal cases are supervised and stage-marked.
- PyQt6 is not installed in the authoring container. Native Linux Qt qualification is **OPEN** until the user runs this release and provides the new report.
- If v2.51 still blocks, the terminal/report `QT_STAGE` identifies the last entered phase. Do not add further UI features before inspecting the exact failing stage and callback.

## Future sequencing

1. Verify native host smoke; eliminate the first observed blocker at its actual owner.
2. Extend Python graph editing via adapter-backed transformations with explicit deletion/replace, calls, function boundaries, effects/dominance analysis and user-facing undo.
3. Audit text editing with temporarily invalid syntax, project/workspace tooling, diagnostics, testing, completion and debugger architecture.
4. Only revisit other language adapters once Python visual/text workflows pass realistic end-to-end IDE acceptance.
