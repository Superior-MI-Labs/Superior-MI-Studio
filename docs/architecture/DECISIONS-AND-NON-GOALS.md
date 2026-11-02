# Studio Architecture — Decisions, Definitions, Non-Goals and Drift Controls

**Rev 3.1, 2026-10-30. This ledger is normative for agents.** If a prior conversation, old release note, or implementation convenience conflicts with an *ACCEPTED* decision below, do not silently reinterpret it. Escalate as a decision proposal backed by tests. If an item is marked EXPERIMENTAL, prove it before promoting to ACCEPTED.

## A. What we are building, in one paragraph

Superior MI Studio is a general, extensible desktop development workbench that treats text programming and visual programming as equally legitimate user experiences. Existing language files remain editable as ordinary code; native program graphs support creative/incomplete work; qualified graph regions can be generated as source; source projections are faithful, with unsupported syntax preserved; synchronization carries versioned provenance and reports conflicts without loss. The existing Qt renderer, recursive scopes, resource explorer, navigation and authoring infrastructure are valuable foundations. Correct architecture is defined by **program semantics, ownership and testability**, not by matching Unreal's appearance.

## B. Formal ADR register

| ADR | Status | Decision | Why / boundary |
|---|---|---|---|
| ADR-001 | ACCEPTED | Document-centered workbench, multiple document kinds, one canonical authority per document/region | Permits source- and graph-owned workflows without dual truth |
| ADR-002 | ACCEPTED | Graph-owned native programming document can save disconnected, invalid and incomplete programs | Authoring freedom is independent of compilation success |
| ADR-003 | ACCEPTED | Save, Validate, Generate, Publish and Run are separate transactions | A failed compiler must never delete drafts or corrupt `.py` |
| ADR-004 | ACCEPTED | Immutable `GraphDescriptor` is presentation contract, not mutable program storage | Avoid a second writable graph registry |
| ADR-005 | ACCEPTED | Language-specific adapters own semantics, effects, bindings, types, lowering and import | Qt cannot prove Python expression behavior |
| ADR-006 | ACCEPTED | Generation uses semantic control structure, never geometry | Canvas x/y is not execution order |
| ADR-007 | ACCEPTED | Initial qualified publish unit is a complete function plus validated dependencies | Node-by-node partial output can silently change behavior |
| ADR-008 | ACCEPTED | Existing `.py` opens source-owned unless explicit conversion requested | Existing user code cannot be dropped on import |
| ADR-009 | ACCEPTED | Text buffer may be syntactically invalid and still savable | Basic IDE parity and non-loss |
| ADR-010 | ACCEPTED | One revisioned transaction mechanism per document; all views share it | Prevent tab/graph/text races |
| ADR-011 | ACCEPTED | Generated source remains versioned derived artifact until explicit publish | Avoid surprise modifications to user source |
| ADR-012 | ACCEPTED | Unknown operation versions and unsupported source are preserved visibly, not guessed or omitted | Future compatibility, trust and correctness |
| ADR-013 | ACCEPTED | Graph presentation (camera, layout, reroute, grouping) has no semantic authority | Deterministic code output |
| ADR-014 | ACCEPTED | Preserve legacy `smi.dynamic-node-lab` prototype schema separately from executable ProgramGraph | Sliders/audio cards are not a programming language |
| ADR-015 | ACCEPTED | Incremental refactor, characterization tests and migration gates before removals | Avoid loss of mature behavior |
| ADR-016 | ACCEPTED | Headless and native Qt host qualification are independent requirements | Avoid false green builds |
| ADR-017 | ACCEPTED | Toolchain execution requires explicit user intent and records source revision | Opening source does not execute code |
| ADR-018 | ACCEPTED | No second real programming language until Python-first and round-trip gates pass | Prevent duplicating immature semantics |
| ADR-019 | ACCEPTED | Operation catalog must be semantic registry-derived, not duplicated across UI/engine | One operation truth and consistent gestures |
| ADR-020 | ACCEPTED | Prefer stable contracts, simplest owner, and deletion of superseded code over compatibility sprawl | Maintenance must not grow faster than capability |
| ADR-021 | PROVISIONAL | Native extension `.smi-graph`, serialized `smi.program-graph`, schema v1 | Freeze after Phase 2 prototype/migration tests |
| ADR-022 | PROVISIONAL | Exact structured ProgramGraph storage representation and control-region encoding | Must be proven by Python graph compiler slice |
| ADR-023 | PROVISIONAL | Function-scoped source map / generated-code import minimum | Must be validated on comments, effects, Unicode and conflicts |
| ADR-024 | PROVISIONAL | Last-valid source projection policy when text buffer invalid | UX should be tested; stale label is mandatory |
| ADR-025 | PROVISIONAL | Whether draft unresolved links are saved as placeholders or explicit intent edges | Must maintain structural integrity while preserving intent |
| ADR-026 | PROVISIONAL | Recovery journal location/retention and disk atomicity strategy on Linux and Windows | Prove failure recovery and permissions behavior |
| ADR-027 | REJECTED | Two independently mutable authorities for same region with automatic timestamp winner | Silent semantic corruption and data loss |
| ADR-028 | REJECTED | Graph editor writes Python by simple edge serialization/string concatenation | Cannot preserve lexical scopes, evaluation order and effects |
| ADR-029 | REJECTED | Use Python `ast.unparse` as lossless formatter for imported source | Does not preserve original formatting/comments byte-for-byte |
| ADR-030 | REJECTED | Universal compiler/AST for all languages before Python is correct | High debt and speculative semantics |
| ADR-031 | REJECTED | Full UI rewrite or general plugin framework as a prerequisite | Unnecessary risk and scope expansion |
| ADR-032 | REJECTED | Treat absence of execution pin as evidence a function call is pure | Python calls may be effectful |
| ADR-033 | ACCEPTED | Universal workspace graph uses shared resource identity, navigation and presentation with specialized document authorities | One canvas can show resource previews/dependencies, but source, visual-program and binary-file owners are not collapsed into a universal mutable graph |
| ADR-034 | ACCEPTED | Resource previews and cross-file edges must be bounded, opt-in, source-evidenced, and typed distinctly from execution wiring | Prevents speculative dependencies, accidental code execution and giant eager repository scans |
| ADR-035 | ACCEPTED | One validated render revision per graph canvas; delayed Qt callbacks may never fetch graph edges/ports from a different active tab | Prevents stale descriptor/raw edge mixing; preserves existing source, graph, and tab authorities |
| ADR-036 | ACCEPTED | Package and asset edges are opt-in, visible-file syntactic candidates with separately selectable layers; require package initializers and keep live source-session authority | Prevents invisible dependency guesses, unsafe scans and conflation with execution wiring |
| ADR-037 | ACCEPTED | Resource relationship inspection reads only the selected canvas's validated GraphDescriptor and matching render revision; endpoint actions route through existing tab sessions | Prevents inactive-tab ownership drift, forged endpoint paths, stale edge navigation and duplicate editors |
| ADR-038 | ACCEPTED | Evidence-line navigation prequalifies exact syntax against the current authoritative source revision before route mutation; non-source target framing reuses current resource cards | Avoids stale-line jumps, second source owners and arbitrary file type editing |
| ADR-039 | ACCEPTED | Until original root tabs are migrated, their session IDs are nonclosable compatibility anchors, independent of other tab counts | Closing a random currentIndex after Qt changes selection must not delete the root session |
| ADR-040 | PROVISIONAL | Independently authored source may reconcile one explicitly selected, fully compiler-proven function; unmodeled regions remain exclusively text-owned | Enables bounded function progress without pretending to import arbitrary Python or changing unrecognized source |
| ADR-041 | ACCEPTED | Source-driven input rewiring may target only existing graph-owned typed pins and uniquely mapped generated producers, with full compiler equivalence before any atomic commit | Extends visual/text interchange without a new AST-to-graph authority or silent graph deletion |
| ADR-042 | ACCEPTED | Independent-source AST may use transient, fail-closed correspondence for uniquely assigned compiler locals and source-owned no-op/documentation statements, followed by the unchanged full compiler proof | Supports natural source spelling without writable source maps, source mutation, or weakening generated-source exactness |
| ADR-043 | ACCEPTED | Independent-source constant conditional syntax may be normalized only for exact bounded graph-supported types and only after both alternatives are independently proven pure literals | Avoid unmodeled evaluation and unauthorized source/graph edits while accepting ordinary Python syntax |
| ADR-044 | ACCEPTED | A release qualification supervisor must bound its entire private process group and preserve an archived durable verdict; the process exit code remains authoritative | Prevent lingering child subprocesses and ambiguous promotion when test wrappers stall |

## C. Vocabulary (agents must use these precise definitions)

- **Source-owned document:** canonical content is the text buffer; graph is derived analysis. A painted graph node is not independently authoritative.
- **Graph-owned document:** canonical content is a saved native `ProgramGraph`; source generation is derived and tied to revision.
- **ProgramGraph:** editable, semantically meaningful operation network with stable IDs, structured scopes, explicit control/value dependencies and incomplete states. Not the same object as GraphDescriptor.
- **GraphDescriptor:** immutable, validated view projection from source, program graph, resource, or legacy prototype. Rendering consumes this object.
- **Prototype graph:** existing `model.py` non-runtime node presentation mockup. Not a Python compiler input unless explicit migration of supported node types occurs.
- **Source island:** an opaque, preserved text region that cannot yet be represented with normal nodes; may be read-only or require explicit ownership switch. Does not imply compilation success.
- **Node instance:** stable program operation in one graph. **Operation definition:** adapter-owned semantics, ports/properties, validations and lowering. **Visual node:** rendering of instance/descriptor with no independent semantics.
- **Connection qualification:** outcome of adapter/schema check; structural drawing alone is not proof of runtime meaning.
- **Semantic validity:** supported operation, scope, ordering and effects proved enough to lower. Different from **structural validity** (file schema and identity consistency).
- **Generate candidate:** immutable proposed code and diagnostics for a specific graph revision. **Publish:** explicit guarded commit to a target file. **Run:** explicit tool invocation on a declared artifact/revision.
- **Dependency closure:** the complete set of required functions/imports/module state/effects and signatures that must be accounted for to publish a safe compilation unit.
- **Source mapping:** provenance between source spans and graph identities at exact versions. Not fuzzy line-number equivalence.
- **Draft:** unfinished content persisted but not implicitly executed or published. **Disconnected:** not linked, but possibly a legitimate function/program entry; disconnection alone is not proof of dead code.
- **Opaque/unknown:** cannot be represented/proven; preserve with limitations. **Invalid:** known violation. **Stale:** derived result refers to an older revision. **Conflict:** competing edits cannot be automatically reconciled. These statuses may coexist.
- **Host-qualified:** native Qt interaction smoke performed on actual target environment with no uncaught callback exceptions or timed-out stages, not a simulated headless unit test.
- **Definition of Done:** baseline parity, positive and adversarial tests, no data loss, owner consolidation, native evidence if UI touched, rollback, updated docs/matrix.

## D. Semantics and user-visible behavior contract

| Scenario | Save Graph? | Generate? | Edit text? | Edit graph? | Result |
|---|---|---|---|---|---|
| Unconnected Multiply node on sketch canvas | Yes | Only independent complete units | Yes in separate source view | Yes | Draft preserved; no implicit Python fragment inserted |
| Missing required branch condition in reachable function | Yes | Block that function and dependencies | Yes | Yes | Node error; old generated code unchanged |
| Two independently complete functions and one incomplete unrelated experiment | Yes | Preview qualified functions; publish if required module closure is satisfied | Yes | Yes | Explicit selection and diagnostics; no silent node deletion |
| Syntax-invalid `.py` typed in editor | N/A | Source-owned graph analysis blocked/partial | Yes, save allowed | Stale projection read-only where unproven | Text preserved exactly, diagnostic shown |
| Source-edited generated graph code (`a+b` -> `a*b`) | Graph remains saved | Pending import/merge | Yes | Yes, but separate revisions | Qualified import may update graph after verification |
| Graph and source edited same function since common base | Yes each | Publish blocked pending choice | Yes | Yes | Merge conflict and both versions retained |
| Unknown future graph operation ID | Read-only recovery or migration-preserving save by policy | Block affected units | Source preview may be shown | Do not mutate unsupported semantics blindly | Unknown raw data preserved and diagnosed |
| User moves nodes, changes color, adds reroute | Yes | Same code hash | Yes | Yes | Pure presentation change |
| User requests Run on untrusted project | Yes | Separate from run | Yes | Yes | Explicit command/permission, no auto-exec |

**Important refinement:** “Only compile valid portions” never means treating a reachable invalid branch as optional. Unit boundaries and dependency closure are semantically checked. Publication is never a naive filter over nodes with green badges.

## E. Architecture test obligations by decision

- ADR-001/010: open one `.py` in two views; edit and undo in either; one buffer, one monotonic revision, no silent overwrite.
- ADR-002/014: save/reopen arbitrary unfinished executable graph; original legacy prototype still loads unchanged.
- ADR-003/007/011: block publish on reachable invalid node; preserve graph and last-good `.py` and source diff.
- ADR-004/013: semantic hash unchanged when camera/layout/zoom/reroute/selection changes.
- ADR-005/019: UI action eligibility parity across menu/search/pin-drag; generator consumes same adapter operation IDs.
- ADR-006/032: multi-effect calls executed exactly once; random screen rearrangement no change in runtime order.
- ADR-008/009/012/029: import complex Python without reformat or silent missing code; invalid bytes/text persist and are diagnosable.
- ADR-015/016/020: no untested broad refactor; 606 baseline and full native Qt stage evidence when changed.
- ADR-017: opening project fixture cannot execute sentinel script; explicit Run records command/environment/source hash.
- ADR-018/030: mock second adapter may project descriptors but not take execution role until Python gate passes.

## F. Non-goals and things we deliberately refuse to build yet

Do not create: custom Python interpreter, graph execution engine, full arbitrary-Python compiler to Graph IR, generalized SSA/CFG optimizer, automatic whole-project rewriter, implicit code execution on save, OS-wide shell runner, AI planning engine inside compiler, remote cloud execution, second file watcher backend, marketplace, complex multi-language compiler framework, universal node palette for every language, speculative state synchronization microservices, theme overhaul or incompatible serialization migration. These are not product rejections forever; they are **scope protections** until measured requirements justify them.

## G. Cross-project integration without contamination

Studio may eventually consume original icon manifests from the Superior MI Visual Atlas and expose asset libraries/previewers. The icon atlas is **presentation metadata**, never a programming operation registry. An image label or icon identifier cannot define code generation. External asset packs are untrusted data until validated. Likewise, future AI assistance, agent tools, inference systems and other Superior MI products may integrate through documented commands/tools. They must not bypass document revisions, schema validation, source mapping, sandbox/trust, or the operation registry. Build integrations as adapters, not hard-coded business-specific logic in Studio core.

## H. Architecture change control

Every significant design change is proposed as:

```markdown
ADR proposal ID / date / owner:
Observed problem with file/line/test evidence:
Existing owner and contract:
Option A / Option B with costs and tradeoffs:
Decision and reason:
Canonical data authority and transaction effect:
Failure cases, compatibility and migration:
Exact tests and host qualification:
Code removed versus introduced:
Rollback plan:
Status: PROPOSED / ACCEPTED / REJECTED / SUPERSEDED
```

A provisional ADR becomes accepted only after a bounded runnable demonstration, negative tests, and one architecture review. A prior accepted decision can be superseded with evidence; do not preserve obsolete abstractions and let two competing policies coexist. End every agent ticket with changed definitions or an explicit statement that none changed.

## v2.96 ADR: same-contract comparison edits and failed-batch isolation

**Decision: ACCEPTED pending native release qualification.** Prefer the existing `_qualified_source_edit_plan` and ProgramGraph command validator over a new AST matcher. Integer `python.less_than` and `python.equal_int` share typed canonical ports, so source edits between `a < b` and `a == b` may be mapped to the same node ID only when full trial lowering proves source equivalence. Other comparison operators are not admitted by name similarity. A failed independent function batch probes one selected region at a time on the diagnostic path to name the first invalid function and its source lines, but may never commit a subset. Recheck whole-graph/source revisions on import; preserve opaque source-owned text. See `PHASE4-COMPARISON-RECONCILIATION-v2.96.md`.

## v2.97 ADR: typed integer comparison family and source parse provenance

**Decision: ACCEPTED for headless qualification; native verification pending.** Extend the existing ProgramGraph operation family instead of introducing a new AST-derived mutable graph. `NODE_TEMPLATES` retains interface authority and `python_lowering.INTEGER_COMPARISON_AST` is the Python adapter's single syntax mapping for `<`, `==`, `>`, `>=`, `<=`, `!=`. All variants keep `py:int` input ports and `py:bool` output, allowing existing operation-replacement commands only when canonical ports match. Generated and independent source edit review use the **same** mapping and full trial lowering, with graph/source revision gates, atomic undo and source retention. Chained comparisons, unproven operand rewrites, unknown syntax and type incompatibility remain unsupported; never silently coerce Python runtime values. Before an independent source AST exists, parser failures report the actual source-owned line/column, not a fabricated function anchor. See `PHASE4-INTEGER-COMPARISON-FAMILY-v2.97.md`.

## v2.98 ADR: QA fixture truth and ephemeral source region evidence

**Decision: ACCEPTED; native-qualified by `qualification-20261102-044314-48735.tar.gz`.** Native GUI regression scenarios are *test clients* of the established compiler and document contracts, not independent sources of truth. In a cumulative smoke suite, construct replacements from current compiler node/line maps and fail immediately on absent, duplicate or no-op edits. Restore the original ProgramGraph state after independent-source scenarios before starting linked-source scenarios. No production exception, bypass or guessed one-edit receipt is permitted to satisfy a brittle assertion. Preserve native CI and host promotion gates.

For independent-author source review, enrich the immutable review receipt with optional original source-owner change-line evidence. Map only unique exact assignment targets within the same explicitly selected named function after full compiler equivalence proof. Ambiguous or missing targets yield *no* line evidence, not guessed locations, and do not create an alternate importer or persistent AST cache. A receipt cannot bypass source text SHA, saved-file/unsaved-revision validation, or graph revision requalification. See `PHASE4-QT-FIXTURE-AND-SOURCE-LINE-EVIDENCE-v2.98.md`.

## v2.99 ADR: one arithmetic adapter and exact negative-literal proof

**Decision: ACCEPTED for headless qualification; native verification pending.** Evolve the existing ProgramGraph numeric operations and Python lowering rather than create an AST importer. The `INTEGER_ARITHMETIC_AST` table is the Python adapter's single operator mapping for `+`, `-`, `*`, `//`, `%`; ProgramGraph owns port identities. Reverse import may recognize a negative integer encoded as `UnaryOp(USub, Constant(int))`, **not** evaluate general unary expressions. Every edit must still satisfy full trial compilation and current source/graph revision checks, with no partial import or source write. Function correspondence remains by explicit unique name; report missing/duplicate definitions without fuzzy matching. See `PHASE4-ARITHMETIC-AND-FUNCTION-IDENTITY-v2.99.md`.

## v2.100 ADR: source correspondence without secondary ownership

**Accepted (headless; native pending).** Explicitly selected independent Python functions must have unambiguous static top-level bindings. Reject detectable source-module rebinding while respecting function/class/comprehension locals. AST statements provide optional original-source line/column spans only after full compiler equivalence proof. Do not persist anchors, infer renames, guess on ambiguous assignment targets or treat receipts as commit authorization. See `PHASE4-INDEPENDENT-SOURCE-ANCHORS-v2.100.md`.

## v2.101 ADR: compiler-proof input-wire reconciliation

**Decision: ACCEPTED for headless qualification; native verification pending.** Two approaches were evaluated: (A) generate a new mutable AST-derived graph document when source references change, or (B) reuse the graph owner's `replace_input` command for **unique existing** same-function values, followed by the existing complete compiler proof. Choose B: stable node IDs, input-wire IDs, types, source-session revision checks and one atomic undo transaction are preserved without an additional graph owner. A changed source operand is only a candidate; if producer identity is ambiguous, a value is not source-generated, a graph operation becomes orphaned, or whole-graph AST/byte proof differs, refuse the **entire** import. Generated-source and explicitly selected independent-function paths use the same qualifier. Neither graph nor source file is changed by review. No implicit rename matching, new node synthesis, or automatic AST-to-graph translation. See `PHASE4-COMPILER-PROVEN-INPUT-WIRING-v2.101.md`.

## v2.106: typed execution-owned input reconciliation

Extend the existing compiler trial and `ProgramGraph.replace_input` to value inputs on typed Bind, Local/Assign, and bounded Repeat nodes. Preserve generated-source exact proof, independent function AST proof, source authority, execution and guard semantics. Never infer a new node or execution connection from edited source. See `PHASE4-EXECUTION-INPUT-RECONCILIATION-v2.106.md`.

## v2.107 ADR: compiler failures explain rather than guess

**Decision: ACCEPTED for headless review; native qualification pending.**
Compare (A) a new source-to-graph AST diagnostics/mapping owner with (B)
read-only explanations derived solely from the existing compiler's parsed
reference/candidate trees. Choose B. On refusal, report the first structural
AST path, syntax category and candidate line where available; bound traversal
and output. Independent Python uses a normalized synthetic AST, therefore a
reported candidate AST line is **not** an original source-file line. The outer
reconciliation exception retains the real selected-function region. No
source or graph mutation, hidden approval, partial commit, fuzzy rename or
persistent source map follows from a diagnostic. Parse the validated canonical
source once per preflight, preserve graph revision and source SHA gates, and
keep all native Qt host promotion requirements unchanged.

## v2.115 ADR — source-owned local trivia without extra graph authority

**Decision: Accepted for headless qualification; native pending.** Extend the ephemeral independent-function candidate (approach B) rather than introducing editable annotation/pass graph nodes (approach A). Restrict normalization to simple local annotations with safe names, and `pass` inside an otherwise populated control suite. Retain exact generated-source proof, original source ownership, full trial compilation, atomic rollback and read-only source receipts. See `PHASE4-SOURCE-ONLY-LOCAL-SYNTAX-v2.115.md`.

## v2.116 ADR — unambiguous local identity independent of statement order

**Decision: headless candidate; native pending.** Reuse the existing ephemeral independent-function AST normalization and the v2.103/104 pure-order compiler proof rather than introducing a graph/source identifier database. A unique missing generated temporary and unique new author local are a deterministic bijection, independent of statement order. Reject conflicting local names and multiple alias permutations; do not relax the full compiler, source revision, orphan, effect or strict linked-source gates. Preserve the authored source exactly and commit only through existing ProgramGraph commands. See `PHASE4-ORDER-INDEPENDENT-LOCAL-CORRESPONDENCE-v2.116.md`.
