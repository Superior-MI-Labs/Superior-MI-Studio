# v2.52 — Function Call GUI/adapter contract correction

## Host failure and diagnosis

Source: v2.51 Linux `qualification-20261030-182611-37074.tar.gz`.
Doctor and 617 headless tests passed. Native Qt reached `QT_STAGE function-call-form` and failed with `AssertionError: Function Call form has no qualified source input`; the modal supervisor rejected the dialog and returned a nonzero qualification outcome, retaining the logs. This was a correctly detected failure, not a successful Qt release.

There are **two** defects, both caused by mixing the four-field qualified Call target with three-field authoring UI expectations:

1. `qt_smoke.py` unpacked a 4-tuple `(scope,names,anchor,callees)` but forwarded positional fields as `(scope,anchor,names,callees)` to `_ask_stored_call(scope,anchor,names,callees)`. The dialog received `anchor` where it expected source-value names, so `value` was not available in the argument combo.
2. `gui.py` used `for scope,names,anchor in candidates` while supplying the 4-field `eligible_composed_call_targets()` result for the stored Call operation. The production creator would fail unpacking before reaching the dialog.

## Architecture choice

Considered (A) changing all adapter Call targets to three fields and re-querying callee signatures at every consumer; this discards useful qualification data and forces unrelated callers to change. Considered (B) adding temporary special-case error handling in the Qt creator and smoke; this hides the mismatched data contract and duplicates knowledge. **Selected (C):** keep the adapter's four-field authority, project a three-field anchor view in the existing `authoring_actions` boundary, and call the dialog through explicit keyword-only parameters. Other composition actions already use the three-field anchor view. The dialog still queries current `qualified_callees` for its selected scope; no shadow registry or state is introduced.

## Qualification and acceptance

Four headless regressions check Call eligibility, uniform GUI anchors, a validated source proposal, keyword-only dialog binding in both production and smoke callers, and the GUI routing through the shared anchor projection. Existing Python-first gate, undo/redo and source review safeguards are unchanged.

The next native Linux run must reach `QT_STAGE function-call-form`, select a qualified `value` input in the visible dialog, produce a source proposal, then complete the remaining native smoke without tracebacks. **Do not claim this gate passed from the headless suite alone.** Failure reports must preserve the last completed stage and prevent installation promotion.

## Subsequent development

Keep Python as the only authoring adapter. After native validation, resume the larger Blueprint-style graph editing milestone with source-backed operations, not a second graph compiler. Avoid treating a green UI smoke as proof that every visual editing gesture is qualified; add targeted host tests for each implemented path.
