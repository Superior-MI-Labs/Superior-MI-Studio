# Architecture source of truth and evidence precedence

1. **Product rules:** `DECISIONS-AND-NON-GOALS.md` (accepted ADRs) and `MASTER-BLUEPRINT-v3.1.md` (target architecture).
2. **Subsystem and migration:** `SUBSYSTEMS-AND-INTERACTIONS.md`, `REFACTOR-AND-CLEANUP.md`, `IMPLEMENTATION-AND-TRACEABILITY.md`, acceptance matrix.
3. **Actual current implementation:** `studio_native/`, `tests/`, `README.md`, `docs/V252-FUNCTION-CALL-AUTHORING-CONTRACT.md`. These control factual claims about what currently works.
4. **Historical documentation:** `history/` and historical v2.50 inventory. They explain rationale but are not authoritative descriptions of v2.52.

The v3.1 documents were developed against v2.50. The Phase 1 code snapshot is v2.53, based on v2.52; see `PHASE1-BASELINE-AND-LIVE-PROJECTION-v2.53.md`. Treat specific line counts, function signatures, failure states and test totals in older docs as leads for verification. Any conflict between an accepted future-design ADR and the current implementation is a migration task, not proof that the code already follows the ADR. Do not covertly modify the product to 'make docs true.' Document the delta and pursue the phase gates.

The v2.50 archive itself is deliberately **not embedded** in this repo copy to avoid duplicating historical application sources. It remains in the prior handoff package. All architecture Markdown, original review history, decision register and acceptance matrix have been copied here for agents.

**v2.54 update:** The shared revisioned source session is implemented in `source_editor.py` and Qt wiring is a host-unqualified candidate. See `PHASE1-REVISIONED-SOURCE-SESSION-v2.54.md`; keep planned compiler and graph-owned schema separate.

**v2.55 host-blocker update:** The user-reported v2.54 native Qt failure has a verified undefined route in independent directory-tab creation. v2.55 also repairs in-place source-document reload identity. See `PHASE1-TAB-ROUTE-AND-SESSION-INTEGRITY-v2.55.md`; do not mark Qt qualified until a clean WolfCat-Studio report.

**v2.56 recovery milestone:** The uploaded v2.55 native report confirms `NATIVE_QT_SMOKE_PASS` with 654 headless regressions. v2.56 keeps draft text undo in `SourceDocumentSession` (bounded deltas), separates it from disk-backed `SourceEditHistory`, and exposes read-only external-change status. See `PHASE1-DRAFT-UNDO-AND-EXTERNAL-CHANGES-v2.56.md`; native acceptance remains host-pending.

**v2.57 keyboard-dispatch correction:** The v2.56 host report failed the source undo gesture despite model-level tests passing. See `PHASE1-DRAFT-KEYBOARD-ROUTING-v2.57.md`; v2.57 retains one source-session history and introduces no new program model. Native acceptance is host-pending.

**v2.58 smoke isolation:** The v2.57 host smoke failed after the source-document stage because the stage leaked an extra Qt source tab into later navigation assertions. Stage runs on its own `NativeLab`; production sessions unchanged. See `PHASE1-QT-SMOKE-FIXTURE-ISOLATION-v2.58.md`. Host qualification pending.

**v2.60 recovery:** `PHASE1-CRASH-RECOVERY-v2.60.md` documents a non-authoritative durable source-draft journal, exact-base restore, privacy and test isolation. 20 new headless tests; host QT qualification OPEN. The single live queue is `docs/agents/NEXT-TASKS.md`; do not use archived T00–T13 as concurrent active orders.

**v2.60 native recovery qualification:** `PHASE1-RECOVERY-QT-ISOLATION-v2.60.md` records the failed v2.59 Qt gate, button-driven interaction repair, independent subprocess, and remaining host test.
