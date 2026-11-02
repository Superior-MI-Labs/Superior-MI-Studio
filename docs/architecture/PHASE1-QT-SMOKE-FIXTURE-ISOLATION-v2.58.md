# v2.58: Native Qt smoke fixture isolation

## Evidence and root cause

WolfCat-Studio `qualification-20261030-215646-6977.tar.gz` passed the earlier keyboard shortcut checks, then failed at `qt_smoke.py`'s `len(w._source_tabs)==1` during the independent-source-tab stage. In v2.57 the document lifecycle smoke had opened an additional Python graph tab for a temporary file; it switched back to the original view without closing the extra. The later call that reloaded the demo source was applied to the active extra tab. The independent-tab check subsequently opened and closed one more tab, leaving the original leaked tab and causing the assertion. This failure does **not** demonstrate a broken production tab registry or a failing undo implementation.

## Compared approaches

1. **Change the assertion to expect two tabs or ignore it. REJECT.** The test would quietly accept state contamination and could later encounter a deleted temporary file or inactive view with stale state.
2. **Close the leaked extra tab and manually restore the main window. NOT CHOSEN.** Shorter change, but relies on fragile knowledge of private routes, session dictionaries, text buffers, and fixture ordering. Easy to break when the lifecycle implementation evolves.
3. **Run the state-mutating document-history stage in its own `NativeLab`. CHOSEN.** One real Qt workbench for the revisioned-document exercise, one original workbench for subsequent navigation coverage. The fixture saves cleanly and closes; it never publishes a temporary tab into the main workbench.
4. **Split the entire monolithic Qt smoke into isolated test cases. DEFER.** A legitimate eventual improvement, but unnecessarily broad for a host qualification blocker and risks discarding visual integration coverage in one pass.

## Contract and tests

- No production `gui.py`, `source_editor.py`, parser, graph, route, or persistence logic is modified.
- `exercise_revisioned_source_session` owns its own window and verifies that two graph views use the same source-session path. The session is clean and window closes at the stage end.
- Main window verifies that its source view and demo document are unchanged by the independent stage.
- The independent tab test records exact source-tab IDs before opening a view and asserts that closing it restores the same IDs. Exact membership is stronger than an absolute tab count.
- New headless static guards ensure the fixture boundary, close call, and before/after tab assertions remain present. These are *not* native Qt execution evidence.

## Acceptance gate

Run `bash ./RUN-ALL.sh` on WolfCat-Studio. Require doctor/headless pass, no uncaught callbacks, all Qt stages (including `source-document-keyboard-routing`, independent-source-tab, resource-tab, and authoring dialog tests) to finish, `NATIVE_QT_SMOKE_PASS`, and retained screenshots. No claims about graph-owned programs, multi-process writes, or recovery were added.
