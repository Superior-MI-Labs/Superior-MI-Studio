# Phase 4: Native generated-Python import and atomic compound commands (v2.77)

**Status:** release candidate; headless proof plus new native Qt smoke stage. Not general source-owned Python-to-graph synchronization.

## Architecture decision

The v2.76 single-change import was correctly owned by Python lowering and an existing graph command. Two possible expansions were considered:

1. **Reparse arbitrary Python into graph-owned operations on each keystroke:** rejected. This cannot prove identity, effects or formatting preservation and would quietly destroy unsupported code.
2. **Keep compiler-backed exact regeneration and expose a transient candidate editor:** chosen. Qt retains only temporary candidate text; it is not the owner of a `.py` document or a new compiler. `ProgramGraph` owns program mutations. `SourceDocumentSession` continues to own independently opened `.py` documents. No automatic disk mutation or execution occurs.

## Integrated behavior

- Visual Program → **Edit Python** opens generated source tied to the graph revision. The code is an *unpublished candidate*, not canonical source.
- **Import into Graph** invokes the existing Python adapter's exact source-map and whole-program re-lowering proof. Up to 32 compatible literal/arithmetical changes can be accepted together. The `ProgramGraph.edit_many` implementation delegates every command to existing `ProgramGraph.edit` on an isolated valid graph and commits the final state once, producing **one revision and one undo entry**.
- Any stale revision, unknown expression, formatting difference, type change, missing mapping or unsupported edit refuses **all** updates and keeps the draft visible.
- **Export Draft As…** writes a new `.py` through `python_edit.create_source_exclusive`; invalid or unsupported drafts can be preserved. The export refuses existing targets and symlinks, uses the same lock owner and never modifies the `.smi-graph`.
- Closing an edited draft asks for explicit discard confirmation. A successful import regenerates the graph projection; graph file saving and Python publishing stay separate.
- Generation, import, export and publication **never run code**. An explicit Run task is a different operation.

## Tests and risks

`tests/test_v277_compound_import.py` proves rollback on an invalid second command, stale revisions, maximum batch bounds, one-step undo, compiler parity, identity/layout preservation and no file mutation. Native `QT_STAGE program-generated-source-import-editor` tests the actual editor, positive multi-edit import, undo/redo, save/reopen, failed unsupported edit and retained export, stale revision refusal, and clean shutdown.

Outstanding: source-owned `.py` to graph reconciliation, comments/formatting preservation, arbitrary multi-function edits, synchronizing several simultaneous views, named local variables and broader Blueprint/IDE workflows. A modal candidate view is a deliberate narrow bridge, not the desired final split-editor interface.
