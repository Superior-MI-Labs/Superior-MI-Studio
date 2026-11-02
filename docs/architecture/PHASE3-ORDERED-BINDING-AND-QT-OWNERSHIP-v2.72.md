# v2.72 — Ordered binding and host Qt smoke ownership

## Evidence

v2.71's WolfCat-Studio host run timed out after `program-qualified-sequential-require`.
`exercise_program_workspace()` creates `fresh_guard` as a new unsaved graph.
The final `w.close()` invokes production `NativeLab.closeEvent()`, which calls
`ProgramWorkspace.confirm_close()` for every graph tab. `QMessageBox.question()`
remained unattended. This was a **test lifecycle mistake**, not evidence the
production discard confirmation is wrong. The nested `tee` pipeline also risked
waiting for process descendants still holding output after the stage timeout.

## Alternatives and decisions

- Disable the application's unsaved-changes modal under test: **rejected**;
  would hide a genuine user-data safety boundary.
- Click all unexpected prompts automatically: **rejected**; could hide dirty
  fixtures and data-loss problems.
- Save the intentionally incomplete graph, assert every program fixture clean,
  preserve real production close behavior: **implemented**. Each stage's output
  is file-backed to avoid inherited pipe lifetime extending supervisor wait.

## Semantic extension

The existing `ProgramGraph` templates and `python_lowering.py` own two typed,
execution-ordered single-assignment capture operations: `python.bind_int@1`
and `python.bind_bool@1`. Each has `exec` and `value` inputs, `then` and `value`
outputs. Source generation binds exactly once when the explicit exec tree
visits the node. The emitted temporary can be used by later data producers
in that execution path, but never before the capture or in a different branch.

These are **not** mutable variables: there is no overwriting, merging of
branches, unrestricted call effects or loops. `python.call` refuses effectful
functions transitively. Incomplete and invalid graphs still persist, but
unqualified programs cannot publish Python. Qt uses existing Node Library and
ProgramWorkspace mutation paths; no second node registry/compiler is added.

## Verification and rollback

Headless regression tests cover typed binding, runtime results, ordering,
wrong-path and before-exec refusal, source mapping, save/reopen, undo/redo,
publication and effectful call boundaries. A separate shell regression
reproduces a detached child keeping stdout open. The Qt stage asserts clean
shutdown and exercises the saved ordered-binding example. Only WolfCat-Studio
can close the native Qt acceptance gate. On any failure, preserve previously
host-qualified v2.69 and use the emitted report; do not promote this release.
