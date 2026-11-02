# Phase 4: Explicit source-owned Python link (v2.78)

**Status:** headless-qualified candidate; native Qt pending. This is an exact-baseline interoperability bridge, not arbitrary Python↔graph conversion.

## Decision: reuse document ownership, not invent a synchronized document store

Two approaches evaluated:

1. **Make ProgramGraph the owner of .py text or construct a unified shadow file model. Rejected.** This would create a second source of truth, undermine source recovery and encoding rules, and lose unsupported Python.
2. **Associate existing owners via a versioned, temporary reconciliation receipt. Chosen.** The Python lowering adapter (`LinkedPythonSource`) holds an in-memory reference to the existing `SourceDocumentSession` and `ProgramGraph`. Linking requires exact saved UTF-8 Python generated from the graph, an unmodified real file and a clean source document. There is no hidden source copy or second parser.

## Invariants and user workflow

- Open a qualified `.smi-graph`. Publish its Python to a **new** `.py` and open that file in Studio's actual Python source editor. In the graph tab click **Link open .py**. A source already open from a prior publication can also be linked when content matches exactly.
- Edit the real `.py` text. `SourceDocumentSession.update` owns the draft, undo, recovery and source analysis; Qt does not own source history. Click **Import open .py** in the graph. Only 1–32 mapped same-type literal or compatible operator changes are eligible. The existing `import_generated_source_edit` proves whole-program exact regeneration on a disposable graph before committing one undoable graph revision.
- Graph and Python source remain independently dirty until users explicitly save each. Import does not save, run or publish code, alter formatting or discard unsupported source. On any exception the entire source draft remains recoverable and graph state remains unchanged.
- The link fails closed when the graph revision is stale, an external edit appears, a source revision moves backward, or a changed saved file has an ambiguous additional unsaved draft. A normal guarded source save remains eligible: the full candidate must still exactly regenerate from the original linked graph. Saving after graph import also preserves subsequent linked edits. No speculative three-way merge or automatic conflict resolution.
- The link is ephemeral (per open ProgramWorkspace), not persisted as identity metadata. It is not yet general bidirectional editing of unrelated `.py` files. Arbitrary comments, formatting, classes, decorators, effects, and unsupported syntax are not converted to nodes.

## Test and cleanup impact

`tests/test_v278_linked_source_reconciliation.py` characterizes exact baseline acceptance, clean source constraints, multiple edits, sequential revisions, separate saves, undo, unsupported code/syntax, graph conflicts, external file races and relink. The native Qt `program-linked-source-document-reconciliation` stage exercises the actual source editor, graph tab, explicit import, undo/redo, two saves and stale-link refusal.

The link lives in `python_lowering.py`, beside existing source-mapped import; no new parser or document model. The Qt workbench only selects existing document sessions and dispatches intent. The active roadmap is `docs/agents/NEXT-TASKS.md`, not this historical decision record.
