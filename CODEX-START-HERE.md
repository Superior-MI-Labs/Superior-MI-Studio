# Codex start here — Superior MI Studio v2.139

## v2.139 — independent-source proof receipts cannot outlive evidence (CI / host pending)

In `python_lowering._independent_functions_plan`, compiler proof previously
checked the source owner/disk, built advisory source line/column spans, then
stamped a review with whatever ProgramGraph revision existed at return.
If source, disk or graph changed during span evidence, the receipt could
misstate the revision and provenance of its approved edits. A single
local preimage guard now checks the live SourceDocumentSession, disk and
ProgramGraph both before and after evidence mapping, and prioritizes
ownership conflicts over stale compiler diagnostics. Existing generated
lowering and import transactions remain the only authorities. Normal
review/import is unchanged; adversarial test coverage is in
`tests/test_v2139_independent_evidence_preimage.py`.
See `docs/architecture/PHASE4-INDEPENDENT-EVIDENCE-PREIMAGE-v2.139.md`.
v2.138 passed headless/native GitHub CI; Linux Mint host report pending.


## v2.138 — source whole-file Up follows the selected graph session (CI/host pending)

`source_go_parent` was the last whole-file Python toolbar path that
called the filesystem provider directly, skipping `_open_navigation_route`.
With a secondary Python graph selected, Up could navigate an unrelated
last-active resource tab instead of replacing the selected tab's provider.
It now delegates the parent directory via the existing Route dispatcher,
which already distinguishes original protected roots from secondary
cross-provider sessions and preserves history/camera identities. Focused
lexical-scope parent navigation remains unchanged. A real Qt
`QT_STAGE source-parent-uses-selected-graph-session` tests
resource→Python→parent→Back on one secondary tab, protected roots and
safe closure, with structural checks in
`tests/test_v2138_source_parent_route.py`.
See `docs/architecture/PHASE5-SOURCE-PARENT-ROUTE-v2.138.md`.
v2.137 passed GitHub headless and native Qt CI. Mint host pending.


## v2.137 — initial source-root focus now refuses before publishing a root (CI/host pending)

An uninitialized protected source root could receive a focused function
route, open the entire Python document and create the root session, then
fail when `navigate_source` discovered that the function scope was gone.
The original file-opening transaction now optionally validates the exact
focus scope through `resolve_source_session_route` using the **same live
SourceDocumentSession** before updating source registries or Qt aliases.
Valid focus retains the whole-file Back history; invalid focus or syntax
cannot create a ghost root. This avoids duplicate source reads and any
compensating rollback. It is not a new parser or tab owner.
The new `tests/test_v2137_initial_root_focus.py`, updated older
characterization tests and native
`QT_STAGE uninitialized-source-root-focus-atomicity` cover both refusal
and successful initial focus while another source view stays intact.
See `docs/architecture/PHASE5-INITIAL-ROOT-FOCUS-v2.137.md`.
v2.136 passed GitHub headless and native Qt CI. Mint host pending.


## v2.136 — original source-root directories belong to the filesystem root (CI/host pending)

The protected Python root could request a directory while the last-active
resource alias still named a secondary tab. The route dispatcher reused
`browse_resource` but without a target tab identity, so it could advance
the secondary's history and show the wrong canvas. The same provider now
preflights `browse_resource(root_anchor=True)` with the protected root's
view preferences, and only binds its root alias after successful resolution.
This is the filesystem mirror of v2.135's source-root protection, not
another tab manager. A prequalified replacement skips re-reading the root's
former directory during alias activation. Existing resource routes,
source/graph owners, editor drafts and root guards remain unchanged.
`tests/test_v2136_resource_root_route.py` and real
`QT_STAGE source-root-resource-anchor-isolation` qualify both refusal and
successful routing with a separate secondary resource tab.
See `docs/architecture/PHASE5-RESOURCE-ROOT-ROUTE-v2.136.md`.
v2.135 passed GitHub headless and native Qt CI; Mint host qualification is
still outstanding.


## v2.135 — first protected source-root alias binds only after proof (CI/host pending)

A cross-provider transition can create an independent Python view on a
secondary resource tab while the protected `source` root remains unopened.
The legacy first-source adapter previously rebound the provider's last-active
source aliases **before** the existing file preflight could refuse. A failed
root open could therefore leave Qt selected on a resource tab while the
source alias/editor had been reset to an uninitialized root. The existing
`_open_python_source_path` now supports one private `bootstrap_root`
parameter: its original source validation and graph projection run first,
then it commits the root alias only on success. The secondary view remains
independent; invalid Python text diagnostics and explicit file-picker
behavior remain unchanged. No new route, parser or source owner. See
`docs/architecture/PHASE5-SOURCE-ROOT-BOOTSTRAP-v2.135.md`.
v2.134 passed GitHub headless and native Qt CI; v2.135 and Mint host pending.


## v2.134 — ProgramWorkspace is not a provider view (CI/host pending)

The shared `_open_navigation_route` correctly identified the selected Qt
page but then read `selected.session_id` before confirming source/resource
type. Native `ProgramWorkspace` has no such session. The route could raise
`AttributeError` instead of refusing an unsupported in-place navigation.
A typed guard in the existing dispatcher now preserves provider, source and
graph ownership. Explicit `new_tab=True` retains its established path.
The native Qt stage checks both refusal routes, unchanged histories/cameras,
source owners and graph revision, and an explicit new-tab success.
See `docs/architecture/PHASE5-PROGRAM-NAVIGATION-BOUNDARY-v2.134.md`.
GitHub CI and the independent Mint host report are pending; v2.124 remains
the latest uploaded host-qualified baseline.


## v2.133 — closing inactive provider alias cannot steal Qt focus (native pending)

`_close_graph_tab` now distinguishes the actual selected Qt page from the
resource/source provider's **last-active alias**. Closing a secondary tab
whose session is still that provider's last-active ID must rebind its
provider root, but may select the root Qt page **only when the closed tab
was the foreground tab**. This preserves a different provider's foreground
selection, history and camera. ProgramWorkspace close confirmation and both
protected root guards remain unchanged. The real native smoke exercises both
source→resource and resource→source inactive-close cases. Three headless
contract tests cover source structure and expected Qt assertions. No new
registry, source owner or navigation method. See
`docs/architecture/PHASE5-INACTIVE-PROVIDER-CLOSE-v2.133.md`.

v2.132 passed both GitHub CI lanes; v2.124 remains the last uploaded Mint
host-qualified baseline. No automatic promotion on GitHub CI alone.

## v2.132 — selected-view alias activation consolidation (native pending)

The existing `_workspace_tab_changed`, `_open_navigation_route` and
`_navigate_history` previously duplicated the same provider-specific
store/activate sequence for already-selected resource or Python tabs. They
now call one private idempotent `_bind_selected_graph_view` adapter that
reuses the original provider-owned `_store_active_*` and `_activate_*`
methods. Only source activation needs to flush the existing pending source
analysis timer. The original protected source-root bootstrap remains explicit
because it can bind a root that is not yet the selected Qt page; do not fold
it into the ordinary selected-view helper. The `GraphViewSessions` history,
Qt page registry, source owner and camera contracts are unchanged. Three
headless tests and `QT_STAGE selected-graph-view-binding-idempotence` test
root/source no-op parity in native Qt. See
`docs/architecture/PHASE5-SELECTED-VIEW-BINDING-v2.132.md`.

v2.131 passed both GitHub CI lanes, but no newer Mint host report than v2.124
has been supplied. No product-release promotion follows from CI alone.

## v2.131 — secondary graph-tab creation stages first (native pending)

`open_resource_in_new_tab` and the already-initialized branch of
`open_source_in_new_tab` now construct their Qt page, canvas and navigation
bar before registering the new provider view/session, source document or
consuming a numeric tab identity. A failed toolbar build refuses without
mutating existing routes, tabs, documents or cameras. The protected initial
Python root's first-file adapter remains unchanged. The existing native
smoke injects failure for both providers and subsequently opens/closes each
tab, while headless tests guard publish-after-stage ordering. No universal
tab controller or additional state owner. See
`docs/architecture/PHASE5-NEW-TAB-STAGING-v2.131.md`. v2.130 passed both
GitHub CI lanes; v2.124 is the last uploaded Linux Mint host-qualified
baseline. Next: inspect activation paths and remove only proven duplicate
alias bindings after native Qt parity; never remove root compatibility
anchors without a replacement contract.

## v2.130 — consolidate Qt tab-close page lookup

The existing `_graph_tab_for_page` remains the only Qt page-to-view registry
reader for activation, navigation and now **closure**. `_close_graph_tab`
removes repeated source/resource `.values()` scans but retains the existing
program close confirmation, protected root guards, GraphViewSessions closure,
view-only source semantics and active alias restoration. Native smoke closes
an inactive secondary resource page while the root is selected, and checks
root identity, route and camera preservation. See
`docs/architecture/PHASE5-SINGLE-QT-TAB-CLOSE-DISPATCH-v2.130.md` and
`tests/test_v2130_single_tab_close_lookup.py`. v2.129 fixed the staging
registry regression and passed both GitHub CI jobs; v2.130 needs independent
native CI and Mint host evidence before promotion. The next cleanup target is
remaining root/secondary activation duplication, **not** removing root anchors.

## v2.129 — correct destination-provider view registration

The v2.128 native CI failed deterministically because the staging refactor
registered a replacement view in the **outgoing** provider's registry instead
of the incoming route's provider. This produced a selected `SourceTabView` with
no registered source owner, detected by the existing relationship-evidence
native smoke. v2.129 keeps the staging-first design, but uses `old_kind` only
for retirement and `route.kind` for registration. Its new test covers both
provider directions; the existing Qt smoke enforces actual source-owner,
history and camera parity, and retains diagnostic context if evidence jumps
fail again. Architecture note: `PHASE5-SECONDARY-PROVIDER-REGISTRY-v2.129.md`.
The v2.124 Mint host baseline remains the last uploaded native PASS; v2.129
needs CI and a fresh local host report before promotion. Do not resume the
independent tab-close cleanup until the failing native test is green.

## v2.128 — staged cross-provider Qt replacement before route publication

The selected secondary graph tab keeps its existing provider view until a
replacement canvas, page, toolbar and title have been constructed successfully.
The original `_transition_graph_tab` remains the single route/session
transaction; it now performs all fallible **preparation** before writing the
source document map, old-view registries, active aliases, camera or history.
Qt `RuntimeError` / `ValueError` while constructing a replacement refuses the
route and discards only the staged page. Native smoke injects toolbar failure
and checks that the original page, source map, route, history and camera survive;
the same route then succeeds after the injected failure is removed. Root
anchors remain protected; no new coordinator, tab registry or state owner.
See `docs/architecture/PHASE5-SECONDARY-PROVIDER-STAGING-v2.128.md` and
`tests/test_v2128_provider_transition_staging.py`. This is not a claim of
full exception atomicity after a Qt replacement commits. The previous uploaded
Linux Mint native PASS is v2.124; v2.128 is host-pending.

## v2.127 — linked-source proof-to-commit receipt guard

`LinkedPythonSource` now snapshots one live `SourceDocumentSession` revision,
text and saved preimage; reviews and imports reject subsequent source/disk
or linked graph-identity changes even if they occur *during* compiler proof.
For imports, the same `_qualified_source_edit_plan()` remains the only Python
admission authority, but the final owner checks run before the single
`ProgramGraph.edit_many()` transaction. No-op imports are checked too.
Unencodable drafts fail through `ProgramGraphError`. The linked owner does not
publish source text, hold a second mutable document or add a lock. Ten
adversarial tests live in `tests/test_v2127_linked_source_snapshot.py`;
architecture note: `PHASE4-LINKED-SOURCE-PREFLIGHT-INTEGRITY-v2.127.md`.
The most recent uploaded Linux Mint host PASS remains v2.124; v2.126 passed
headless/native GitHub CI, and v2.127 needs its own host report.

## v2.126 — independent-source conflict receipts and captured revision integrity

The existing independent-source compiler planner captures the live `SourceDocumentSession`
revision and text once. Its AST, source hash, line evidence and review receipt
must all represent those exact bytes. It rechecks the session revision/text and
`inspect_external()` after proof (including failure diagnostics) and the import
path performs a final external-file check before `ProgramGraph.edit_many`.
A reentrant source edit or external write during qualification now refuses with
`GraphConflict` and leaves graph state unchanged; a non-UTF-8-encodable draft
is a clean `ProgramGraphError`, never an unhandled encoder exception. No locks,
new mutable source snapshots, second source map, extra parser or Qt changes.
Regression tests: `tests/test_v2126_independent_source_snapshot.py` (6).
The v2.125 GitHub headless and native Qt CI jobs passed; v2.124 remains the
latest uploaded Linux Mint native host PASS pending a newer report.

## v2.125 — bounded source admission and indexing consolidation

The independent-function planner now uses two private helpers *inside the existing
Python adapter*: a transient top-level function index and a preflight of
existing graph-owned keyword-call targets plus module-level identity/shadow
checks. Both consume the current parsed source module and generated compiler
baseline, not a new document representation, parser, or mutable registry.
The full graph trial remains the only edit admission authority. Source bytes,
graph revision, atomic import and refusal semantics are unchanged. Tests:
`test_v2125_independent_preflight_contract.py`. The uploaded v2.124 Linux
Mint qualification report passed all 1,350 tests and native Qt smoke;
v2.125 remains host-pending.

## v2.124 — bounded independent-function diagnostic retries

When a selected authored function contains only source-owned trivia or syntax
that normalizes to the exact graph-generated baseline, it cannot explain a
failed full-batch compiler proof. The existing failure-isolation loop now
compares the *ephemeral normalized candidate* to the already-indexed graph
function before retrying a trial compilation. It never compares unnormalized
source trivia or reindexes the baseline. Changed candidates still get isolated
with the original source line-span for diagnostics, and no partial graph edit
is committed. `tests/test_v2124_independent_diagnostic_efficiency.py` verifies
compiler call counts and non-mutation for both skipped and genuinely changed
regions. The v2.121 host report `qualification-20261108-125446-79635.tar.gz`
records passing doctor and native Qt smoke; v2.122 and later versions still
need their own Linux Mint host evidence.

## v2.123 — ephemeral independent-source compiler candidate consolidation

The accepted v3.1 refactor roadmap keeps Python parsing, source correspondence
and compiler admission in one language adapter, while source documents and
ProgramGraph remain independent authoritative owners. The v2.123 source
candidate has separated the existing temporary proof-function preparation
into three narrow helpers **inside** `python_lowering.py`: safe syntax/trivia
normalization, unambiguous generated-local correspondence, and existing
keyword-call canonicalization. The original AST is deep-copied before any
candidate transformation. The selected-function module indexes, revision /
digest conflict gates, complete graph lowering, all-or-nothing import and
unsupported-source refusals are unchanged. No second source mapping, parser,
operation vocabulary, graph store or persistent state was introduced.

Tests: `tests/test_v2123_independent_candidate_boundaries.py` and the existing
v2.103–v2.121 source reconciliation suites. Native Linux host promotion still
requires its own report. v2.122 GitHub CI passed; latest uploaded Linux Mint
host PASS remains v2.120. Continue comparing headless and native gates
independently, and do not retire root-tab anchors before v2.122 host evidence.

## v2.122 — qualified root navigation before Qt tab selection

Previously, a route opened from the original filesystem tab into an already
initialized source root could switch the selected Qt tab before the Python
owner validated a requested scope. Rejected routes must now leave the source
and resource histories, tab selection and active aliases intact. The existing
`_navigate_source_document_in_tab` owns both selected-source and root-anchor
routes; no extra parser or view session was introduced. Cross-provider
transitions also check Qt page membership before committing registry changes.
Tests: `tests/test_v2122_root_route_atomicity.py`, existing v2.84–v2.86
route tests, and native Qt `protected-root-source-refusal-atomicity` stage.
The candidate is not host-qualified until its full native report is reviewed;
v2.121 GitHub CI passed, and v2.120 has the last uploaded Linux host PASS.

## v2.121 — portable source checkout release proof

The release builder accepts an arbitrarily named source checkout while validating
the source installer version against the authoritative installer module. It
still emits the exact versioned archive root required by the installer,
rejects mismatched source versions, maintains manifest hashes, and refuses
overwriting an existing archive. Public README prose is not release metadata;
CI checks installer, GUI and release-pipeline contracts instead. The v2.121
candidate requires fresh host native qualification before promotion.

## v2.120 — no-op annotation and static guard proof

The existing independent-function proof may erase *only in its transient AST*
bare `int`/`bool`/`str` local annotations of names already assigned in the
function or present in its parameter contract, and pass-only `if` guards whose
condition normalizes to an exact Boolean constant. It refuses dynamic guards,
truthy integers, unknown locals, unsupported annotations and any control suite
that would be emptied by normalization. No source writes, graph node synthesis,
new local-name authority or generic AST importer. The full graph lowering
proof and source/graph revision gates remain required.

## What Studio is

Superior MI Studio is becoming a unified visual/text development IDE: one navigable project graph, Blueprint-grade programming interactions, authoritative language-aware source buffers and executable graph documents, and extensible file/asset capabilities. Python is the **first** language, not the eventual limit. Visual Studio Code is the workbench reference; Unreal Blueprints is the visual authoring reference. Do not mistake design-roadmap documents for implemented features.

## v2.119 conditional literal proof and complete qualification supervision

Qualified, explicitly selected independent Python functions may spell an existing `py:int` or `py:bool` literal as a fixed `X if condition else Y` expression. Both arms must be exact constants of the same supported type (never a dynamic/effectful arm); graph edits are authorized only by the existing full trial compiler, and generated-source linking stays byte-exact. A 4096-node cap protects each transient source AST. `RUN-ALL.sh` archives `qualification-verdict.txt` before completion; `install_linux.run_qualification` bounds the entire process group, kills its descendants on timeout, returns 124, and preserves older managed installs. This is additional supervision, not a replacement for the Python doctor or native Qt gate. Tests: `test_v2119_source_constant_proof.py` and `test_v2119_release_supervision.py`. Candidate v2.119 is native pending; last provided host-qualified v2.115.

## v2.118 bounded integer and Boolean expression normalization (native pending)

Only the temporary independently authored function proof candidate may fold constant integer arithmetic into a literal representing an *existing* ProgramGraph literal node. Supported pure operations: unary `+`/`-`, binary `+`, `-`, `*`, nonzero `//` and `%`, each with operands and results inside a strict 63-bit magnitude. There is no `eval`, source execution, AST-to-node construction, text rewriting, additional source map or compiler authority. The existing complete re-lowering and atomic graph import checks remain mandatory. Generated-source import stays byte-exact. Fixed integer comparisons and Boolean `not`/`and`/`or` on exact constants can likewise normalize only existing Boolean literal graph nodes; dynamic and chained forms refuse. Regressions: `tests/test_v2118_constant_expression_proof.py` and `tests/test_v2118_boolean_expression_proof.py`. Most recent host-qualified baseline remains v2.115 pending a newer report.

## v2.117 multi-alias source matching and bounded doctor qualification

The independent-source normalization can pair **multiple** renamed generated assignments only through unique, dependency-resolved, pure-expression AST witnesses. Source names are never persisted, and any ambiguous/effectful/raising identity refuses rather than guessing. A source-only reorder of pure operations with no graph edit is accepted as an informational no-op only after the same suite-local dependency proof. Generated-source imports remain strict. Tests: `test_v2117_multi_alias_proof.py` and neighboring v2.116/v2.103 suites. A stalled doctor now exits as failed qualification with an archived diagnostic (default 240s; `SMI_DOCTOR_TIMEOUT`), not an unbounded hold. Test: `test_v2117_qualification_watchdog.py`. Last host-qualified remains v2.115.

## v2.116 reordered local-value correspondence

A single uniquely missing compiler-generated assignment target and a single new local target may be matched without relying on assignment position, including within a structured branch. The existing whole-graph compiler must still prove a valid dependency reorder and one undoable graph update. Never guess among multiple aliases or mutate original Python text. The original positional multi-alias path remains bounded to unchanged generated-name order. See `tests/test_v2116_structural_local_identity.py` and the v2.116 architecture decision.

## v2.115 source-only local syntax boundary

Independent Python function reviews may remove **simple, non-executing syntax only in an ephemeral proof candidate**: local `name: int|bool|str = value` becomes an ordinary assignment; redundant `pass` statements can be omitted from already populated `if`/`else`, `for` and `while` bodies. Empty suites and complex annotations are not normalized. No source mutation, new ProgramGraph nodes or persistent mapping is allowed. The full compiler is the acceptance authority; generated-source import remains byte-exact. Original AST spans for annotated values remain read-only evidence. See `tests/test_v2115_independent_source_syntax.py` and milestone document.

## v2.114 independent-source local correspondence boundary

Selected independently authored functions may use a human-readable spelling of a uniquely assigned compiler-generated `_smi_value_N` temporary, and source-only leading docstrings/direct `pass` statements. This is a transient, conservative AST alpha-normalization for the **existing compiler proof only**, not an editable source map. Original source bytes, docstrings and comments stay with `SourceDocumentSession`; compiled graph publication cannot reproduce docstring metadata. Renaming parameters, generated identities with repeated writes, ambiguous moves, nested scopes, global or nonlocal declarations, and unsupported expressions are refused. Final graph trial, revision/digest and atomic import checks are unchanged. Tests: `test_v2114_independent_local_correspondence.py`.

## v2.113 keyword-call proof boundary

Source-owned keyword calls may normalize only into temporary AST candidates when every explicit argument is a local name, the callee has a matching, unshadowed graph-owned definition and the complete trial graph reproduces the normalized AST. Generated-source imports remain exact; the original source text and AST receipts retain keyword order and exact argument spans. No second importer, rewrite of source files, fuzzy names or callable search. The prior compiler preflight also retains these rules: the independent-source review may reuse a synchronous compiler preview and parsed canonical AST **only within the same graph-revision preflight**. Generated-source callers use a fresh preview; commits requalify all source/graph revisions and hashes. A single candidate AST statement pass replaces repeated passes without becoming a source map. User installation is via one ZIP and inline Bash; no separately downloaded shell script is necessary. The bundled Python installer continues to own all cleanup and native qualification.

## Current source of truth and reading order

1. `AGENTS.md`: guardrails, engineering workflow, subsystem authorities and test expectations.
2. `docs/architecture/DECISIONS-AND-NON-GOALS.md`: accepted architecture and explicit non-goals.
3. `docs/agents/NEXT-TASKS.md`: **only active implementation queue** and latest release/host evidence.
4. `docs/architecture/REFACTOR-AND-CLEANUP.md` and `docs/architecture/SUBSYSTEMS-AND-INTERACTIONS.md`: owners and consolidation map. The v3.1 master blueprint is an intended direction, **not** executable authority.
5. Relevant tests, current code and focused milestone docs. Prioritize actual code/tests over historical release narratives.

## Current evidence and qualification

- **Working source candidate:** v2.120. The restricted compiler can reconcile explicitly selected functions from independently authored Python through full graph re-lowering proof, one undoable transaction and no implicit source writes. Integer comparisons `<`, `==`, `>`, `>=`, `<=`, `!=` and integer arithmetic `+`, `-`, `*`, `//`, `%` each use a single AST mapping per family. Negative integer literals are reversible without evaluating arbitrary unary expressions; malformed source reports source-owner line/column. No arbitrary source import, implied rename matching or partial commit. v2.100 rejects explicit shadow bindings of selected top-level functions and reports source-owner statement spans; both are read-only AST evidence, not persistent ownership. **v2.101** additionally reconciles selected arithmetic/comparison operand wires to existing same-function values through ProgramGraph.replace_input and whole-graph re-lowering; no topology guesses or second mappings. **v2.102** extends that same proof to existing Boolean Not/Select, pure call arguments, and Return/Return Flow wires, with no node creation or structural control imports.
- **Last confirmed native Linux/Qt PASS:** v2.115, report `qualification-20261102-104724-64648.tar.gz` (doctor and `NATIVE_QT_SMOKE_PASS`, including complete integration shutdown). Neither headless checks nor CI substitute for WolfCat-Studio native qualification. v2.120 is a candidate; v2.115 has full native host proof. Historical root-tab and fixture defects are documented in the milestone records.
- **Architecture:** `SourceDocumentSession` owns authoritative Python text and revision/recovery; `ProgramGraph` owns native visual program state, commands and undo; `python_lowering.py` owns only compiler proof/publication/reconciliation; `GraphDescriptor` and resource/source projections are read-only; `GraphViewSessions` owns tab history/camera; Qt owns presentation. There is **no universal mutable graph owner** for all file types.
- **Source safety:** Unsupported/ambiguous Python remains source-owned and cannot be silently compiled, discarded, or overwritten. Reviews are informational; import must check current source revision/digest, graph revision, exact function identity, and full graph proof again before commit.

## Engineering and release procedure

Treat features as architecture decisions first. Compare reuse of existing owners versus new infrastructure before writing code; prefer the former. Use small focused test loops, then batch related implementation, tests, documentation and cleanup. Avoid stale version assumptions and new modes without an owner contract. For native GUI regressions, inspect exact tab/canvas revision, Qt object lifetime and active selection before changing assertions.

```bash
python3 -m unittest discover -s tests -p 'test_v296*.py' -v
bash scripts/agent-verify.sh --headless
# Only on Linux with PyQt6; a necessary release-promotion gate:
bash scripts/agent-verify.sh --native
```

For each release: prefer `python3 scripts/build_release.py --qualify-headless --output /path/to/versioned.zip` (one existing agent headless gate plus deterministic archive), validate archive manifest; run isolated packaged headless installation; provide only the release ZIP and an inline Bash command to extract its existing `install_linux.py`, run native qualification, extract fresh logs, safely clean previous versions **only after success**, and launch. Do not push, commit, change local tools, or delete the user's functioning installation without explicit permission or the established successful qualification gate.

## Next planned work

1. Native qualification of v2.120; v2.115 is the verified host rollback baseline.
2. Deepen typed source/graph reconciliation with qualified input rewires, stable function anchors, explicit conflicts, and more supported operations **only where compiler equivalence is proven**. Avoid a second AST graph importer.
3. Continue unified workbench/root-compatibility cleanup after the existing navigation and Qt contract regressions pass.
4. More language adapters and extensions come **after** the Python/source/workspace contracts stabilize, not to meet a superficial feature count.

Detailed historical migrations, failed releases and ADRs belong in `docs/agents/NEXT-TASKS.md` and `docs/architecture/`. Do not copy them into another growing handoff.

## v2.105 current boundary
The v2.103 compiler proof now extends to contiguous pure generated assignments
inside each independent structured if/else and for/while execution suite. It
never moves statements across branch/loop/control/effect boundaries and it is
not a general AST-to-graph importer. `test_v2104_nested_roundtrip.py` proves a
real graph-owned branch rewire, unchanged external text and atomic undo/redo.
The qualified release-builder flag invokes existing headless tests; native Qt
host promotion remains separate. Review
`docs/architecture/PHASE4-BRANCH-LOCAL-RECONCILIATION-v2.105.md` first.

Independently authored functions may reorder adjacent pure generated assignments when needed for a compiler-proven existing-wire reconfiguration. Temporary numbering is reconciled against stable graph node-line receipts, not a second map. Scope, source revision, graph revision, effect-order and forward-dependency restrictions remain authoritative. The full semantic proof and atomic graph owner are unchanged. Use `tests/test_v2103_pure_order_reconciliation.py` before extending this further.

## v2.105 handoff

Branch/Require condition inputs and execution-ordered call arguments are now
qualified using the *existing* input-replacement compiler proof. Review
`tests/test_v2105_control_condition_reconciliation.py` and
`tests/test_v2105_execution_call_argument_reconciliation.py` before further
changes. Unchanged execution paths and error effects are essential. The
Inspector's original condition-expression source spans are advisory; the source
owner and compiler remain authoritative.

## v2.106 handoff: execution-owned data inputs

The established source compiler now handles bounded input rewires for `python.bind_int/bool`, `python.local_int/bool`, `python.assign_int/bool` and `python.repeat_int` without introducing new graph commands or mutable source maps. Count edits match the generated Repeat's one-time evaluated bookkeeping assignment, not the `for` expression; the whole-function proof verifies the unchanged guard and effects. The read-only source evidence supports repeated mutable-slot targets through occurrence IDs only after compiler qualification. Use `tests/test_v2106_state_and_repeat_reconciliation.py` and the preceding v2.105 control-condition tests before extending this. Native Qt qualification remains the host release gate.

## v2.107 handoff: compiler refusal diagnostics

`python_lowering._source_ast_mismatch` is a bounded, read-only witness to
structural AST differences in an already-refused source import. It does not
qualify edits and must never be used as a source-to-graph identity map. The
existing full trial graph compiler remains the only proof; independent-function
errors also retain the authoritative source-owner function line range. Read
`tests/test_v2107_reconciliation_diagnostics.py` before changing these messages.
The generated baseline is parsed once per import preflight, not repeatedly.
Native Qt qualification of v2.107 has not been provided; v2.111 is the current candidate.

## v2.108 handoff: exact source-evidence ownership

The read-only `_independent_change_lines` projection retains per-function
assignment occurrence counts; never use counters leaked from an indexing loop.
The same compiler-validated review identifies the actual changed input operand
for arithmetic/comparison, Not, Select, call and Return graphs, rather than
highlighting an entire generated assignment. Literal/operator change spans
select only the RHS expression; an operator token alone has no AST location.
Missing or ambiguous matches produce no receipt, never a guessed source anchor.
Tests: `tests/test_v2108_source_receipt_ownership.py` and the older v2.100,
v2.105, v2.106 source-span suites. Source text and ProgramGraph are unchanged
until explicit import requalifies the entire edit.

## v2.109 handoff: definition-time module identity and AST-index consolidation

`python_lowering._module_function_binding_conflicts` inspects syntax evaluated
while top-level functions and classes are defined: decorators, defaults,
annotations, class bases/keywords, lambda defaults and explicit class-body
`global` writes. Delayed function/lambda bodies do **not** create static
module-level bindings merely by declaring a local with the same name. This
check is conservative static evidence, not whole-program Python dataflow.
Review/import still use the authoritative graph compiler and revision checks.

On a failed multi-function reconciliation, first test only changed selected
function regions to locate the culprit; unchanged regions must not cause
repeated full compiler trials. Source-receipt evidence is collected once per
canonical/authored function AST. Tests: `test_v2109_module_definition_binding.py`
and `test_v2108_source_receipt_ownership.py`. Native Qt host verification is
still required before release promotion.

## v2.110 handoff: one module identity scan per source review

`python_lowering._module_function_binding_conflicts(module, selected)` accepts a
name-to-exact-function-AST mapping, traverses the independently authored module
once, and returns sorted shadow-line receipts by name. Do not restore a per-name
module traversal or introduce a parallel function-name resolver. A bare module
annotation does not rebind the target; its expression still receives the normal
static definition-time checks. Source receipt indexing no longer recomputes
Return nodes after its existing single AST pass. Tests are in
`tests/test_v2110_module_identity_batch.py`. The full compiler proof, same
source/graph revision gate, and one undoable transaction remain mandatory.

## v2.111 handoff: class-global binding integrity and indexed function resolution

A selected graph-owned top-level function can be shadowed by a *class* body
that explicitly declares `global`, even through imports, nested definitions,
except targets, or pattern captures. `python_lowering._module_function_binding_conflicts`
checks those writes with class-scope ownership; normal class locals and
comprehension iteration names do not become module writes. Recursively nested
class bodies are inspected separately, without misclassifying their enclosing
class-local names. Function signatures/default expressions are definition-time,
method bodies are deferred. `tests/test_v2111_function_scope_identity.py`
is the regression contract. The independent review indexes source and graph
top-level definitions once per batch; it retains exact-name matching and
full compiler proof, source/graph revision guards, and atomic graph commit.
This is conservative static syntax, not dynamic Python execution analysis.
