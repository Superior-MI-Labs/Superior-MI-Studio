# v2.64 — Graph-owned visual editing, first native Qt milestone

## Source identity and evidence

- Base: delivered v2.63 release, host-qualified on WolfCat-Studio in `qualification-20261030-225341-128006.tar.gz` (748 headless, three Qt subprocesses, Python-first gate PASS).
- v2.64: Python graph-owned authoring UI and 4th native Qt qualification process. Headless tests and ZIP packaging are separate from native Qt qualification.
- The artifact remains research software; no Python generation, interpreter execution, source reconciliation or language extension is claimed for ProgramGraph.

## Architectural alternatives

A. **Reuse the legacy `model.py` prototype Draft editor:** rejected. The prototype is presentation-oriented, and its node mutations bypass graph-owned semantic revision/persistence rules.

B. **Create a separate new Qt graph canvas/editor:** rejected. This would duplicate pan/zoom, hit testing, node rendering, connection routing, minimap and future Blueprint controls.

C. **Add an explicit ProgramGraph source to the existing GraphCanvas:** implemented. ProgramGraph retains all editable state, exposes a derived graph projection through `semantic_contract.describe_graph(..., origin='program')`, and accepts only revision-checked edit commands. The Qt ProgramWorkspace is a view/controller; its node dictionaries are disposable.

## Included workflow

1. File → **New visual program** or **Open visual program (.smi-graph)** creates a program tab; opening an already-open document activates the existing tab rather than creating another owner.
2. Create and select functions with the compact function selector; each function graph has stable node IDs and its own camera identity.
3. Place structural `python.literal`, `python.add`, `python.multiply`, and `python.return` templates from the graph context menu, Node Library, or Add Node chooser. Their ports are typed `py:unknown`, by design; semantics are **unqualified**.
4. Drag an output pin to an input pin; structural validation checks pin direction, execution relation and function containment. Undo/redo, move, disconnect and selected-node deletion use the same ProgramGraph transaction API.
5. Save and reopen incomplete `.smi-graph` documents; edits never auto-publish or run Python. Save is guarded against stale disk preimages and symlinks; existing source/document writer remains unaffected.
6. The Qt acceptance has one **independent program-subprocess** that constructs functions, creates and connects nodes via a real pin gesture, verifies undo/redo, saves/reopens, and checks rendering. It must produce `NATIVE_QT_PROGRAM_PASS` before graph integration runs.

## Additional correctness controls

- `remove_selection` is one bounded graph-owner transaction that removes selected nodes and incident edges atomically; undo restores the same identities.
- `ProgramGraph.dirty` compares canonical content against the saved graph digest rather than incorrectly treating a valid but whitespace-formatted JSON document as edited. The exact disk bytes remain separately tracked for conflict refusal.
- A graph input pin's connected visual state derives from the validated graph descriptor rather than from legacy Draft state.
- Scene rebuild is deferred until after a pin-release/move event has returned, avoiding deletion of live C++ graphics objects during event dispatch.
- Ctrl+S dispatches to the current graph document; the legacy `Save As` path refuses while a visual program tab is active instead of writing unrelated draft state.

## Known limitations and next gates

- Native Qt host test is **required**; a clean headless test count is not proof of GUI behavior.
- Graph-owned operations are structural templates only; no Python generation, side-effect qualification, parameter/return compiler contracts, or callable code semantics exist yet.
- Graph editor currently offers function selection, not authoring of function inputs or signatures from the GUI. These exist at the ProgramGraph API but need a complete UI/semantic review.
- Save As for graph-owned documents is deliberately disabled pending a separately guarded copy/fork transaction. A false Save As is worse than an explicit refusal.
- Wiring is structural, not source-owned. A disconnected graph and missing required pins are valid saved documents, but not executable.
- Large graph virtualisation, drag-compatible suggestions, collapsed graph regions, comments, debugger and IDE tooling remain planned.
- Reconcile `ProgramGraph` operation/port schema with a bounded Python lowering adapter **before** claiming callable visual functions, and preserve source-owned `.py` authority for existing code.
