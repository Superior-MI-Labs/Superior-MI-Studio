# Archived proposed execution tickets (v3.1)

Historical proposal only. Current execution authority: `../../agents/NEXT-TASKS.md`.

## 3. Recommended first 14 agent work tickets

Each ticket is deliberately small enough for one agent context and one review. Dependency numbers refer to previous tickets. Do not silently start a later ticket while an earlier required gate is failing.

| Ticket | Prerequisite | Owner focus | Deliverable | Required proof |
|---|---|---|---|---|
| T00 | None | Lead/release | Confirm actual target repo, commit/archive, clean worktree; compare shipped v2.50 | Report changed files and provenance; no code changes |
| T01 | T00 | QA/native | Host Qt baseline, doctor and 606 test rerun | Logs/screenshots with timeout/exception status; do not infer PASS |
| T02 | T00 | Architecture/static | Code import graph, file-writer table, mutable state and write-path table | Evidence-backed module/line map, review signoff |
| T03 | T01,T02 | QA/Python | Golden Python/graph/save corpus and characterization snapshots | Runnable expected fixtures; no production changes |
| T04 | T03 | Core/document | Minimal `TextSnapshot`/`DocumentSession` contract and headless two-view test | One buffer/monotonic revisions; no duplicate authority |
| T05 | T04 | Python adapter | Parse in-memory source snapshot; path facade preserved | Unsaved valid text updates graph, exact old projections unchanged |
| T06 | T05 | Text/persistence | Save syntax-invalid source and preserve encoding; guarded disk preimage | Invalid/Unicode/CRLF/external-change/undo tests |
| T07 | T06 | Qt/doc | Replace source editor dirty alias and tab divergence with session-owned state | Native multi-tab/close/undo/preview tests |
| T08 | T07 | Graph schema | Freeze ProgramGraph v1 sample data/operations, structural vs semantic validator | Human-reviewed ADR + golden JSON; legacy prototype unchanged |
| T09 | T08 | Graph core | Pure transaction and deterministic graph save/read/recovery | Arbitrary isolated/missing node draft survives; no geometry semantics |
| T10 | T09 | Graph UI | Descriptor `program` origin, route and graph-owned tab | Native edit/open/save/reopen/camera tests |
| T11 | T10 | Python compiler | Bounded graph-to-Python grammar with stable operation definitions | Two-function demo and exact runtime behavior |
| T12 | T11 | Generation/publish | Diagnostic closure + preview and guarded publication | Partial draft doesn't corrupt last-good code; stale target refused |
| T13 | T12 | Mapping/reconcile | Supported generated source edit imported, conflict and unsupported paths | 3-way text/graph tests; no loss |

**Next tickets after T13:** UI direct-manipulation parity, structured Python branches/loops, Qt smoke stage decomposition, IDE language-server/debugger integration and mock adapter tests. No automatic extra language feature work.

### Start assignment (copy to the first programming agent)

> **Ticket T00/T02 only.** Do not change application semantics. Compare the supplied v2.50 archive with the live repository and inventory every code-owning subsystem: mutable document buffers, graph registries, source writers, JSON writers, operation catalogs, Qt authoring branches, navigators, undo stacks and qualification gates. Produce a dependency diagram and `ARCHITECTURE-OWNERSHIP-AUDIT.md` citing actual file/function/line evidence. Run 606 baseline tests (or report exact deviation); gather native Qt host qualification if feasible. Rank only confirmed duplications, and propose the smallest next vertical slice with tests. Do not start ProgramGraph compiler work until Phase 1's document contract is stable.

