# v2.14 - Host crash recovery and guarded installation lifecycle

## Evidence

Host report `qualification-20261029-015405-216757.tar.gz` had a passing doctor suite and a failing Qt smoke test. `_refresh_whole_file()` returned to whole-file display after navigating a focused scope, but preserved the prior `source_scope`, and the test replaced the PythonDocument directly before refreshing. The breadcrumb function correctly refused the nonexistent old scope. This is a state lifecycle error, not a reason to weaken focus-route validation.

## Decision / code changes

- Normalization stays in the existing view owner: `_refresh_whole_file` sets `source_scope='module'` together with whole-file graph and mode. `_navigation_route` derives a canonical module route whenever display mode is whole. `source_crumbs` validates scopes only for focus mode and uses module for whole mode.
- The native Qt smoke now reproduces the exact prior-document -> focused function -> new-document -> whole-file transition, checking mode, scope, and toolbar restoration. The existing 302 headless tests are preserved; additional tests cover canonical crumbs and safe install boundaries.
- No source parsing, return edge generation, Python editor mutations, or graph authoring logic changed.

## Installer alternatives

**A: add `pkill -f` and `rm -rf` into the user's paste command. Rejected.** This risks unrelated processes, other projects and diagnostic evidence; a broken ZIP could erase the working version.

**B: bounded deployment script in the release archive. Selected.** Standard-library `install_linux.py` validates ZIP paths and CRC, targets only an exact app command launched from one managed version directory, sends SIGTERM with a bounded wait (no automatic SIGKILL), installs to a versioned project folder, runs full doctor + Qt smoke, updates an existing desktop shortcut, and *only on full success* removes exact older app folders and matching generated logs. The latest report is retained. Symlinks are never removed by cleanup; unknown folders/files are left alone. If a separate process still occupies an old app directory, it is retained. Requalification of an identical installation is idempotent.

A failure at any gate retains the previous app directories and reports. The script uses no sudo. It can be tested headlessly without any cleanup via `--headless --no-launch`.

## Qualification

- Headless suite: 308 tests PASS in this build environment.
- Archive integrity, clean extraction, archive-run doctor: required before delivery.
- Linux native Qt: unavailable in this environment; host report is required before declaring visual qualification.

## Follow-up

Once host Qt passes: resume independent GraphViewSession ownership, descriptor-only rendering, verified vs uncertain execution-flow visualization, adaptive graph layout/dock area management and, finally, a read-only second language adapter. Do not duplicate parser, resource provider, or Qt renderer for new tabs.
