# v2.148 — Native workbench commands versus retained prototype

## Observed ownership drift

Even after v2.147 routed Save/Save As by selected owner, ordinary File
New/Open and Ctrl+N/Ctrl+O still created or opened the legacy prototype
JSON graph. The Graph menu exposed prototype-only string/custom nodes,
implicitly opening Legacy / Dev and making the IDE appear to change
program semantics. ADR-014 preserves the prototype format, so deleting
`model.py` is not justified; normal commands must not operate on it.

## Considered designs

- Leave normal menus as-is, add view-sensitive command wrappers and a new
  router: rejected as unnecessary extra state and confusing aliases.
- Move the prototype actions under existing View > Legacy / Dev and give
  native `.smi-graph` File New/Open and Ctrl+N/Ctrl+O: selected. Existing
  `ProgramWorkspace`, `ProgramGraph`, `new_graph`, `open_graph` and
  `create_node` remain responsible; no new controller is introduced.

## Cleanup

Four unreferenced GUI entry points were removed:
`NodeItem._at_graph_resize_grip` (the active gesture calls
`_resize_corner` directly), `NativeLab._create_qualified_branch`
(the existing semantic action catalog already owns this operation),
`NativeLab.is_port_connected` and `NativeLab.source_nodes`.
The still tested `NativeLab.rewire_python_input` was preserved.
Prototype New/Open now activate the retained legacy page only after
their original admission checks succeed.

## Acceptance

- The full headless doctor and native offscreen Qt gates must pass.
- `QT_STAGE native-program-and-legacy-command-ownership` exercises
  actual File QAction shortcuts, native create/save/open, and explicit
  prototype New/Edit/Save with the old JSON schema retained.
- No compiler, persistent document owner, file format, execution,
  extension API or release pipeline changed.
- Linux Mint native host qualification remains separate from GitHub CI.
  Revert this bounded patch if existing command parity fails.
