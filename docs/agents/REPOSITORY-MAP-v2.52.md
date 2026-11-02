# v2.52 observed code ownership and dependency map

This inventory is from the uploaded v2.52 ZIP, not v2.50. Counts are snapshots, not quality scores. Re-run `python3 scripts/repo_inventory.py` after code changes.

| Owner/module | Current responsibility | Architecture direction |
|---|---|---|
| `studio_native/gui.py` (~5133 lines) | Main PyQt6 workbench, canvases, events, menus, cross-subsystem coordination | Move language-specific policy out when touched; do not wholesale split because of size |
| `studio_native/qt_smoke.py` (~1771) | Native Qt integration smoke | Split by stable stage boundaries only when verifying parity and failure handling |
| `studio_native/python_graph.py` (~1566) | AST parsing, scope graphs, source projections | Reuse parser; eventually support in-memory revisioned snapshots; preserve opaque semantics |
| `studio_native/python_authoring.py` (~1531) | Qualified Python source operations | Evolve as language-owned semantic edit adapter, not Qt commands |
| `studio_native/python_edit.py` (~615) | Safe source proposals, preimage checks, undo/persistence | Preserve guarded writer; distinguish buffer transactions vs disk publish in future |
| `studio_native/semantic_contract.py` (~445) | Validated descriptive graph model | Remains immutable graph *view* contract; NOT a second editable source of truth |
| `studio_native/model.py` (~289) | Legacy draft/template graph and JSON | Keep legacy compatibility; not an executable ProgramGraph |
| `studio_native/source_connection.py` | Python input/output connection qualification | One adapter-owned preflight feeding every GUI gesture |
| `studio_native/authoring_actions.py`, `operation_catalog.py`, `authoring_contract.py` | Adapter-backed operation discovery/actions | One operation capability inventory; prevent duplicated eligibility logic |
| `studio_native/source_editor.py` | Source editor integration | Future shared live buffer revisions and undo |
| `studio_native/presentation_state.py`, `graph_layout.py`, `edge_presentation.py` | View-state/layout/wire presentation | Keep separate from executable control/data semantics |
| `studio_native/graph_routes.py`, `navigation.py`, `graph_surface.py`, `docking.py` | Routing, camera, graph view and docks | Preserve one tab/view session authority; test Qt interaction deeply |
| `studio_native/resource_graph.py` | Bounded filesystem visualization | Filesystem resource view is not executable programming authority |
| `tests/` (~70 unit test files) | Most characterization and correctness gates | Preserve and extend before refactor |
| `scripts/python-first-gate.py` | Python program construction check | Required gate |

## Observed internal imports

`gui.py` imports most model, semantic, navigation, authoring and presentation modules; it is a coordination hotspot. `python_authoring.py` imports `authoring_contract`, `python_edit` and `python_graph`; `python_edit.py` imports `python_graph`. `semantic_contract.py` has no relative imports. Do not create reverse dependencies from `python_graph` or semantic contracts back into Qt.

## v2.52-specific facts and risks

The new `docs/V252-FUNCTION-CALL-AUTHORING-CONTRACT.md` records an adapter/GUI contract repair: adapter call targets contain `(scope,names,anchor,callees)` while creator UI consumes a uniform `(scope,names,anchor)` view. Four additional tests protect this boundary. Prior v2.51 work improved modal supervision; this does **not** constitute a new v2.52 host Qt PASS. Include the exact current fixture whenever refactoring the operation catalog, function call UI or native smoke.

## Current constraints / what not to conflate

- `smi.dynamic-node-lab` JSON prototype vs future executable graph document: distinct types and migrations.
- Published Python on disk vs unsaved text editor draft vs proposed generated Python: distinct revisions with explicit transitions.
- `GraphDescriptor` view snapshot vs future mutable semantic `ProgramGraph`: different roles.
- Text code that does not parse must still be preservable; a stale graph may be shown **only when marked stale**.
- Pointer/camera/graph location and wire geometry are presentation, not source execution order.
- `RUN-ALL.sh --headless` is not the full native smoke; stop claiming otherwise.
