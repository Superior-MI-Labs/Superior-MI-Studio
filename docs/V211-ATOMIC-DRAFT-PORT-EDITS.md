# v2.11: Atomic draft graph edits and descriptor consumption

## Baseline / two approaches

A. Rewrite the full inspector and introduce a separate draft graph model with observers. **Rejected:** duplicates state and expands Qt complexity.

B. Keep `model.py` as sole writable draft authority; copy and validate edits, then publish a new state and rebuild the existing scene. **Chosen:** no extra registry, stable IDs, and one contract at the renderer boundary.

## Changes

- `model.transaction(state, change)` preflights every candidate against the existing draft validator and the shared `describe_graph` contract. Invalid edits or exceptions never modify the caller's state.
- Draft edge validation also refuses mismatched connected types and multiple wires into the same input, including loaded JSON documents. These constraints match the established `connect()` guard.
- `NativeLab.commit_draft_change()` is the sole commit path for draft graph-structural changes. The visual adapter no longer paints port topology from a stale snapshot after adding/removing/editing draft pins.
- `NodeItem._ports_for_view()` uses validated descriptor ordering for source, resource, and draft. Settings-only synthetic nodes remain the documented exception.
- Draft create/delete, canvas connect/delete, inspector port edits/defaults, title, and accent commit through the same transaction. Row/section controls remain local UI state; source-backed Python files remain guarded separately.
- Native Qt smoke creates, edits, rejects and deletes a real draft port, verifies refreshed Qt descriptor and port identities, and captures `draft-transaction.png`.

## Limits / qualification

Headless suite: 291 tests passing. Native PyQt6 unavailable in the builder; `RUN-ALL.sh` on Linux Mint must qualify the new inspector path and capture screenshot evidence. No claim that the updated native Qt smoke passed is made before host evidence.

## Next

1. Qualify v2.11 on WolfCat-Studio. Triage any Qt inspector lifetime or screenshot failures before expanding features.
2. Move remaining non-port appearance and control-row update lifecycles through existing validated view/presentation state where appropriate. Do not turn controls into a second executable graph.
3. Normalize adapter declarations for proven execution and call effects, then test a minimal read-only second language producer using the existing descriptor/scene, no second Qt renderer.
4. Use host screenshots to prioritize clipping, overlap, and nested camera issues, avoiding visual rewrites without evidence.
