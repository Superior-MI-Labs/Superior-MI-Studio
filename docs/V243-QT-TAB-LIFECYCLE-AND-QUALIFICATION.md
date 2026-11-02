# v2.43 — Qt tab lifecycle and honest qualification

## Evidence and fault

The user-supplied `qualification-20261029-213422-8331.tar.gz` for v2.42
recorded 549 passing headless tests and `NATIVE_QT_SMOKE_PASS`, but the
Qt log contained **seven uncaught Python callback tracebacks** from
`NativeLab._workspace_tab_changed()`. Three dereferenced `python_doc=None`
while evaluating `eligible_parameter_returns()`. Four dereferenced a
`GraphCanvas.graph_contract` before its initial `rebuild()`.

## Architectural decision

- **Rejected:** local `None` guards in individual Python eligibility functions,
  `getattr(canvas, 'graph_contract', None)` patches in Qt consumers, or a second
  GUI-side eligibility table. These conceal the ownership boundary.
- **Selected:** the existing `authoring_actions.available_actions()` alone
  authorizes qualified source creations and already treats a missing document
  as no actions. The library renders that set; it never reevaluates adapter
  predicates. An unloaded canvas has a real, explicit empty descriptor state
  at construction and replaces it when `rebuild()` resolves the graph.

The existing `GraphViewSessions` and graph resolver remain the owners of routes;
source mutations and their safety rules are unchanged.

## Qualification policy

- `qt_smoke.py` records any uncaught Python slot exceptions reported through
  `sys.excepthook` and refuses the final PASS marker if any occurred.
- `RUN-ALL.sh` independently rejects a Qt log containing uncaught Python
  tracebacks even when the subprocess returns zero, and retains the report.
- Smoke explicitly switches between an unloaded source tab, temporary legacy
  graph tab, and resource tab before the normal interaction suite.
- Regression shell tests inject a traceback with process exit 0 and verify
  failure, preserved logs, and no unsafe `--launch`.

This is a focused lifecycle/ownership correction. The Python-first editing gate
and visual authoring semantics are unchanged. Host qualification on Linux Mint
is **pending**; a headless PASS is not native Qt evidence.
