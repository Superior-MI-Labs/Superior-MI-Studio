# v2.62: committed revision integrity and source-session synchronization

## Evidence and limits

- Authoritative baseline: packaged v2.61 source, `qualification-20261030-223508-109809.tar.gz`; 712 headless PASS, independent native Qt recovery, document, and integration PASS, Python-first gate PASS.
- v2.62 changes are qualified headlessly, not on the user's host until a new report is supplied. No source-level claim of universal cross-process compare-and-swap.
- No new source writer, program IR, Qt graph renderer or language adapter.

## Root problem

A committed graph edit or committed Undo/Redo used `reload_python_source()` after the guarded writer returned. This called the general reload/discard UI and accepted whichever disk revision it happened to reread, without identifying the exact bytes published by that transaction. A concurrent writer could change the bytes between publication and reload. Multiple views also require that the shared `SourceDocumentSession` object remain stable.

## Alternatives

1. Keep generic reload and refresh opportunistically. **Rejected:** loses revision identity and may display unrelated source.
2. Create a second immutable document view manager and mirrored graph state. **Rejected:** unnecessary authority and synchronization debt.
3. Reuse one history transition and one existing session reload method with an **exact expected raw revision**. **Implemented.** `SourceEditHistory.transition()` returns committed bytes after guarded publication. `SourceDocumentSession.adopt_committed_revision()` checks the original open revision, refuses dirty drafts, verifies the file has precisely the committed bytes, and reloads in place. GUI no longer invokes the general discard dialog as the post-write step.

## Other correctness closure

Python source `# coding:` changes must never make the parser analyze different text than the editor displayed. Candidate bytes are decoded under actual Python encoding detection and compared against the editor-facing text before graph qualification and publication. Compatible encoding changes update the session's encoding metadata after saving. Incompatible reinterpretations are refused without writing the file.

## Tests and acceptance

- 11 new headless tests exercise exact adoption, shared session identity, intervening disk change, dirty-draft refusal, wrong preimage, failed history state preservation, Undo/Redo, invalid Python source, GUI call-site routing, and encoding declarations.
- Existing Python-first construction gate and all prior regression tests must remain green.
- Native Qt integration must check successful same-session adoption and committed Undo/Redo across the integration fixture. This remains a host-only gate.

## Known limitations and next work

- Advisory `flock` serializes cooperating Studio writers only. A non-cooperating program may overwrite the file after any verification; subsequent saves must reject stale bytes.
- Committed source history and unsaved draft history remain deliberately separate. Full interleaving semantics, external merge/rebase, and a graph-owned executable document are **not delivered**.
- Keep source-owned Python correct before beginning `ProgramGraph` v1. A single native semantic graph owner should be added only after structural/persistence feasibility tests establish its need and boundary.
