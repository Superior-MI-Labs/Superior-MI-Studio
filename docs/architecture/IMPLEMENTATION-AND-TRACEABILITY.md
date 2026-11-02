> **Repository integration note (v2.59):** This design originated against v2.50 and has since evolved through v2.59. Code and tests in the current archive are factual authority; historical counts and tickets are not current status.

# Studio v3.1 — Traceability, Execution Tickets and Agent Guardrails

**Status: authoritative engineering handoff companion; no code changes are claimed.** The master blueprint explains why; the subsystem and refactor plans define what and where; this file says how an agent can make small, reviewable changes without losing the project direction.

## 1. Mandatory document reading order

1. `README.md` — mission, baseline, package contents, test limitations and explicit start instruction.
2. `docs/architecture/MASTER-BLUEPRINT-v3.1.md` — full product vision, design and phase gates.
3. `docs/architecture/DECISIONS-AND-NON-GOALS.md` — accepted ADRs and vocabulary; resolves ambiguity.
4. `docs/architecture/SUBSYSTEMS-AND-INTERACTIONS.md` — responsibility and allowed interactions.
5. `docs/architecture/REFACTOR-AND-CLEANUP.md` — actual evidence, file hotspots, cleanup and refactor order.
6. This execution file; `docs/architecture/ACCEPTANCE-MATRIX.csv`; `docs/architecture/history/Source_Inventory_v2.50.json`.
7. Existing project `README.md`, `docs/PYTHON-FIRST-READINESS-GATE.md`, `docs/V230-OPERATION-SCHEMA-AND-FUNCTION-BOUNDARIES.md`, `docs/V242-COMPOSABLE-PYTHON-DATAFLOW-AND-IDE-REVIEW.md`, `docs/V249-FUNCTION-AUTHORING-MILESTONE.md`, `docs/V250-QT-QUALIFICATION-AND-REVERSIBLE-SOURCE-EDITS.md`.

Do not claim an archived ZIP is the user's current Git HEAD; compare actual repo status and uncommitted changes first. Do not erase or overwrite unknown user source, sessions, logs or project directories. Work in a branch/worktree or isolated copy, and produce a tested patch/ZIP with a rollback plan.

## 2. Requirements → owners → acceptance gates

| ID | User/product requirement | Authority / subsystem | Baseline / current gap | Gating tests | Phase |
|---|---|---|---|---|---|
| REQ-01 | Text editor is first-class and holds unsaved source | `DocumentSession` + source buffer | Qt dirty state vs disk-only `PythonDocument` | P1-01..P1-05 | 1 |
| REQ-02 | Visual graph builder permits arbitrary incomplete drafts | `ProgramGraph` | `model.py` drafts are non-executable | P2 graph-save tests | 2 |
| REQ-03 | Source AST projects faithful visual structure | Python adapter + `GraphDescriptor` | Strong implementation, file-backed | P0 goldens, source corpus | 0/1 |
| REQ-04 | Visual operations generate real Python | Python graph lowering | No graph-owned compiler | P3 qualified generation suite | 3 |
| REQ-05 | Incomplete required logic cannot corrupt published code | Generation dependency closure | Needs new graph compiler validator | P3 negative branches/effects | 3 |
| REQ-06 | Edit generated Python and map supported changes back | Python importer + provenance | Source-to-graph exists, reverse sync absent | P4 supported/import tests | 4 |
| REQ-07 | Unsupported source remains recoverable | Opaque source islands and conflict service | Some opaque graph projections exist | P4 unsupported/complex code | 4 |
| REQ-08 | Text and graph cannot silently conflict | Session and mappings | No live source/graph shared base | P1/P4 concurrency | 1/4 |
| REQ-09 | Unreal-like node creation and wiring | Action catalog + Qt gestures | Qualified actions exist; drag eligibility gaps | Native E5 tests | 5 |
| REQ-10 | Typed roles, control/data pins, no invented purity | Graph schema + adapter | Some verified roles/effect evidence | Effect/dominance golden tests | All |
| REQ-11 | Function definition and invocation distinct | Graph model + Python adapter | Present in source projection | signature/call/return tests | 3/6 |
| REQ-12 | Whole-file and focused function views | Navigation, projection, view state | Implemented, complex scene geometry | Native navigation/camera tests | 0/5 |
| REQ-13 | IDE tabs, explorer, commands, panels | Workspace, routes and document sessions | Existing PyQt6 workbench | Multi-view/close tests | 1/7 |
| REQ-14 | Stable graph presentation on ordinary source edits | Presentation state and provenance | Position-based source IDs | Identity continuity tests | 4/5 |
| REQ-15 | Additional languages eventually | Adapter contract | Python-only source provider | Mock second adapter tests | 8 |
| REQ-16 | No extra graph interpreter/compiler framework | Language runtime/tool integration | Python actual runtime | Architecture import and Run tests | All |
| REQ-17 | No accidental code execution on file open | Tool trust boundary | Source AST parse is static | Sentinel test | 0/7 |
| REQ-18 | Clean, maintained architecture | Refactor ownership and branch policy | GUI/projection mega-methods | RF negative+parity tests | All |
| REQ-19 | Native Linux qualification and safe installs | `RUN-ALL.sh`, `qt_smoke.py`, installer | v2.50 host status unqualified here | Native smoke and rollback | 0+ |
| REQ-20 | Original Visual Atlas integration remains optional | Asset pack adapter/presentation | External icon atlas exists | Asset metadata validation | Later |

## 3. Current execution authority

`docs/agents/NEXT-TASKS.md` is the **single live work queue**. The originally proposed T00–T13 sequence is preserved in `docs/architecture/history/ORIGINAL-EXECUTION-TICKETS-v3.1.md` for provenance, not as a second list of open tasks. The acceptance matrix retains the fine-grained test obligations and their separate headless/native statuses.

## 4. Agent behavior/quality contract

- **Before coding:** restate exact observed user behavior and ownership; inspect existing implementation and docs; compare at least two approaches including modify-in-place versus a new module; explain why chosen approach reduces future debt.
- **Scope selection:** do not add a new framework just because an existing method is long. Change the correct owner; remove old path only after parity tests, not by leaving long-lived shims.
- **Implementation:** small transactional change; preserve exact source bytes outside intended edits; no Python-specific logic in Qt core; no compiler-by-string-concatenation; no duplicated operation list; explicit versioning for new file formats.
- **Testing:** include positive path, invalid inputs, stale revision, broken references, Unicode/CRLF, effect order, unknown semantics, external-change and native UI if touched. Test failures must not be hidden by broad exception catches.
- **Diagnostics:** explain capability refusal, error provenance and exact revision; failing compiler does not delete work or replace last-good source.
- **Review:** show before/after dependency arrows and proof against architecture invariants; measure code removed/reused/added; identify any unresolved debt and next bounded ticket.
- **Release:** actual host smoke before promotion, safe installer, rollback and evidence tarball. A README line claiming success without test log is not acceptable.
- **Context limits:** one ticket at a time; no unsupported sweeping implementation. If context is exhausted, stop with a handoff containing current state, tests, risk, exact next command and unchanged assumptions.

## 5. Mandatory patch report format

```markdown
# Studio Patch Qualification
Ticket ID / phase / branch / commit / archive checksum:
Actual repository compared with v2.50 baseline:
Scope and user-visible behavior:
Existing source owner and intended data authority:
Option A vs Option B (incl. maintaining existing code):
Architecture decisions reused / proposed / changed:
Files/functions reviewed and exact responsibilities:
Files/contract changed:
New code introduced vs existing code removed:
New/changed file writers, registries, action catalogs (ideally NONE):
Supported/unsupported semantics and failure modes:
Source/graph revision and conflict handling:
Tests before and after; commands + counts + output:
Native Qt: PASS / FAIL / BLOCKED and evidence path:
Performance measures when relevant:
Compatibility, recovery and rollback:
Integrity and user-data-loss checks:
Go/no-go judgment and next smallest ticket:
```

## 6. Architecture compliance checklist

- [ ] Source/graph ownership is singular for each document or region.
- [ ] Command paths do not bypass document revisions or adapter semantics.
- [ ] GraphDescriptor remains immutable; Qt holds only presentation/transient state.
- [ ] Every operation definition has one canonical registry entry; no duplicate dispatch lists.
- [ ] Graph edits are undoable and do not depend on node screen position.
- [ ] Invalid source and incomplete graph drafts save without loss.
- [ ] Generated code has exact source/graph version, toolchain target and source mappings.
- [ ] No effectful call duplication or dropped reachable control flow.
- [ ] Existing Python projects remain readable with comments, Unicode and original semantics intact.
- [ ] External edits and stale analyses cannot silently overwrite work.
- [ ] Legacy prototype documents reopen unchanged.
- [ ] No new Qt dependency in core/adapter, no auto-exec on file open.
- [ ] All existing tests pass and new negative tests demonstrate the change.
- [ ] Native Qt qualification exists for interaction changes.
- [ ] Explicitly retired code paths are removed once safe; no indefinite duplicate compatibility layer.
- [ ] Decision ledger, acceptance matrix, requirements and documentation updated.

## 7. What to preserve from today's development practice

Keep the Python-first quality gate, source preimage checks, in-process source edit undo with backup recovery, native Linux Qt screenshots and timeout logs, launch scripts that refuse to promote failed builds, a file-based delivery artifact and small reversible patches. Improve those mechanisms in place; do not assume a full CI rewrite is a prerequisite to architectural work. Preserve the careful historical research on returns, execution lanes, nested scopes, minimap camera identity and actual host failures. Those lessons should become golden acceptance tests before anyone consolidates the corresponding implementation.
