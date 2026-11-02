# v2.48: Native Qt qualification contract repair

## Host failure being corrected

Report: `qualification-20261030-163027-31369.tar.gz` (October 30, 2026).
Headless doctor passed, but `qt_smoke.py` failed at the obsolete
`len(qualified_operations('python'))==15` assertion. The v2.47 adapter has
16 qualified operations, including `python.assign-source-local.v1`.
The GUI builder map already included the sixteenth operation. An adjacent
assertion expected only 15 buttons and a stale list of 15 Qt object names;
those would have failed immediately afterward.

## Root correction

- Native Qt smoke now checks that the actual Qt creation-button ID set matches
  the adapter's qualified operations ID set. It validates names are distinct,
  plus the new variable-builder identity and existing stable entrypoint.
- The headless suite scans the *actual* Qt builder mapping from Python syntax,
  comparing it to the adapter's catalog without requiring PyQt6.
- Headless regression refuses literal catalog/builder counts in the Qt smoke.
- The older Python capability test now tests required semantics instead of
  freezing the total number of adapter operations.

This changes qualification, not programming semantics or source mutation.
No new catalog is added, and no Qt production feature is rewritten.

## Validation

- Execute `bash ./doctor.sh` and `python3 scripts/python-first-gate.py`
  before packaging.
- Run `bash ./RUN-ALL.sh --headless` for the release evidence bundle.
- **Real Linux Mint native Qt host** must run the default `RUN-ALL.sh` to
  close native qualification. Headless tests cannot establish QWidget behavior.
- The failed v2.47 host report remains useful failure evidence, not a pass.
