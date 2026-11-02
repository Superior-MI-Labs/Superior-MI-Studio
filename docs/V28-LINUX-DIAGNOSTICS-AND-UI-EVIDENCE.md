# v2.8 — Linux launch safety, qualification packaging and visual review evidence

## Why this patch was necessary

The prior installation response used `set -euo pipefail` in a copy/paste block intended for an interactive terminal. When `test-qt-offscreen.sh` returned nonzero, the shell could honor `errexit` and close the terminal window before the user read the failure. **This is an observed defect in the recommended invocation, not confirmed evidence of a Qt renderer crash.** Two failure modes remain possible on the host: a shell exiting early and a genuine Qt failure. v2.8 distinguishes them with persistent reports.

## Architecture and choice

- **Rejected:** add new Python startup recovery framework or catch-and-ignore Qt exceptions. This would obscure real failures, alter semantics, and duplicate launcher logic.
- **Accepted:** update the existing launcher, make the offscreen smoke reuse that entrypoint, and add a thin report-only orchestration shell script. Source parser, interface validation, return routing, and source editor are unchanged.
- No synthetic graph nodes, mutable semantics, adapters, second GUI renderer, or new persistence authority.

## Changes

1. `launch-linux.sh` handles interactive Qt launch, Qt offscreen smoke, and existing headless `--test` from one interpreter resolver. It no longer `exec`s the GUI. Interactive stdout/stderr are retained as `~/Downloads/SMI-NodeLab-Logs/launch-*.log` while preserving the actual Python process exit code. Missing PyQt6 yields a direct package-install recommendation.
2. `test-qt-offscreen.sh` invokes `launch-linux.sh --qt-smoke`. Both routes now agree on the interpreter.
3. `RUN-ALL.sh` runs doctor and native Qt smoke sequentially in independent subprocesses, retains both exit statuses, writes separate logs/screenshots, and produces a `qualification-*.tar.gz` **even when a test fails**. Default runs tests only, `--headless` skips Qt with an explicit unqualified label, and `--launch` launches the editor **only after both tests pass**.
4. `studio_native/qt_smoke.py` optionally emits a `return-boundary.png` from the actual expanded v1.8 source graph after validating the data/control exit geometry and movement/camera pan. This improves the visual record beyond the pre-existing final-loop screenshot. Both screenshots come from native Qt, not simulation.
5. `gui.py` uses one `APP_TITLE` constant to show the correct build label and eliminate obsolete v2.5 title strings.
6. `tests/test_v28_launch_qualification.py` tests pass/fail/skip/launch paths, report preservation, screenshot naming, shell syntax, invalid options, and strict parent-shell continuity with scripts in paths containing spaces.

## Verification performed in packaging environment

- `./doctor.sh`: **269 passed**, Python bytecode compilation, graph/scope fixtures, presentation contract checks; no failures.
- New release-shell tests: **5 passed**, all included in 269.
- `bash -n` for the modified shell scripts: passed.
- `RUN-ALL.sh` failure branch: doctor passed; Qt returned exit code 3 with an actionable PyQt6-unavailable message; logs and `.tar.gz` were preserved. This was an **expected infrastructure failure** and is not a GUI qualification pass.
- Byte-identical to v2.7: `python_graph.py`, `semantic_contract.py`, `exit_routes.py`, `source_editor.py`.
- **Qt renderer not exercised here.** PyQt6 is not installed and cannot be fetched in the build environment. The package must be qualified on the Linux Mint host before claiming the new screenshot or GUI behavior works.

## Linux user acceptance

1. Install to a fresh versioned project directory. Do not use `set -e` in the interactive terminal; use the README's isolated `bash <<'BASH' || ...` block.
2. Run `bash ./RUN-ALL.sh --launch` (default without `--launch` is tests only). It reports the exact `.tar.gz` to upload.
3. Verify `return-boundary.png`: expanded `nested_expression`, the typed value dot and white completion marker, both edges physically attached and unclipped. Verify `qt-smoke.png` too.
4. Manually move the source `total` node, pan/resize the nested function, collapse/expand it, and ensure wires reanchor to the same semantic interface. Inspect `early_exit` independently.
5. If anything fails, upload the **newest `qualification-*.tar.gz`** from `~/Downloads/SMI-NodeLab-Logs`; if the interactive GUI alone fails after the tests, upload the matching `launch-*.log` too.

## Architectural priorities for the next patch

1. **Host Qt evidence first.** Fix any actual exception/crash, paint clipping, pin endpoint/port alignment, or scene-Z errors observed. Do not add a workaround until the source of the failure is understood.
2. **Descriptor-driven renderer migration, one vertical slice at a time.** Move port affordances and validated endpoint geometry away from Python-specific GUI dictionaries while preserving the same data/flow/boundary identities. Keep tests that compare raw graph identities before/after projection.
3. **Execution certainty/role visibility.** Unverified Python calls, exceptional exits and dynamic dispatch should be visually distinct from proven control edges, without manufacturing white wires.
4. **Only then, minimal second-language adapter** in read-only mode with tests for opaque types, provenance, unknown effects and syntax-derived scopes. It must consume the existing canonical contract and use the same Qt renderer.
