# Superior MI Studio — canonical implementation queue

**Source candidate:** v2.124 (independent-function diagnostic retry consolidation; local headless candidate, native host pending). **Latest uploaded Linux host qualified:** v2.121 (`qualification-20261108-125446-79635.tar.gz`: doctor 1,338 tests PASS, `doctor_status=0`, `qt_status=0`, `CHECKS_PASS`, `NATIVE_QT_SMOKE_PASS`). **v2.123 GitHub CI:** headless and native Qt jobs PASS on commit `e36ee9b` (CI is not a Linux Mint host report). **Earlier verified host baselines:** v2.120 and v2.115. Historical v2.82/v2.83/v2.84/v2.86 failures are retained below for root-cause context. Do not repeat outdated v2.81-only baseline claims. The installer cleans managed previous builds and auto-launches only after native qualification.

**Product direction:** One VS Code-style workspace and navigable graph, Blueprint-grade visual interactions, interchangeable source and visual programming where semantics can be proven, a growing set of file/asset previewers and relationship providers. Python is the first language, **not** the only target. Source, graph and binary resources keep specialized authoritative owners; shared presentation/tabs do not imply a universal writable AST.

## Active sequence

| Priority | Work | Required proof / no-go |
|---|---|---|
| 0 | **Obtain v2.122+ Linux Mint host qualification** | The uploaded v2.121 report passed doctor and native Qt. Newer versions passed their respective GitHub CI jobs but have no host report. Keep the existing installer verdict and rollback gates; GitHub success is not local-install evidence. |
| 1 | **Source/graph reconciliation and compiler proof consolidation** | v2.123 separates three transient proof stages in `python_lowering.py`; v2.124 skips proof-identical source-only regions during failed-batch diagnostics. Next inspect deeper conflict explanation and source/graph admission paths with characterization before refactoring. v2.95 added atomic multi-function selection; v2.97 completes all six conventional typed integer comparisons with shared compiler mapping and improves independent-source parse diagnostics. Refuse unsupported AST, fuzzy renames and partial imports. |
| 2 | **Unified tab, route and root compatibility cleanup** | v2.122 makes already-loaded protected root source navigation qualify before switching from a resource tab and preflights cross-provider page membership before registry mutation. Run native `protected-root-source-refusal-atomicity` and complete Qt host qualification before retiring more compatibility branches. Retain root anchors while still required by original file-open semantics. |
| 3 | **Conservative resource capabilities** | Existing previews, imports, literal-reference evidence, relationship inspection, precise source jumps and visible-hop search are implemented. Prefer usability/diagnostics over a recursive filesystem index; static edges are not proven runtime dependencies. |
| 4 | **Future IDE/language support** | Run/debug/LSP/DAP, other languages and an extension host require stable adapter and execution contracts. Do not build speculative infrastructure before core Python round-trip milestones qualify. |

## Implemented and qualified baseline

- v2.53–v2.62 source document revision/recovery, safe guarded writes and isolated Qt tests.
- v2.63–v2.65 graph-owned `ProgramGraph`, stable persistence and native editing.
- v2.66–v2.75 Python compiler, typed execution, conditional branches, bounded Repeat, state and ordered calls (restricted, validated subset).
- v2.76–v2.79 generated source import, real `.py` exact-baseline link, independent saves, repeat Undo/Redo link validation, and qualified source-trivia preservation. v2.79 **host-qualified**.
- v2.80 **candidate:** reusable resource previews for images and saved-source symbol summary; source-literal asset-reference edges. Seven headless tests.
- v2.81 **host-qualified:** real Python nodes/edges embedded in the resource canvas, valid unsaved revisions, invalid-draft hiding, namespace isolation, image previews and relation candidates. Native Qt smoke and doctor PASS.
- v2.82 **not qualified (native Qt failure):** secondary cross-provider tab transition now resolves source through its actual `SourceDocumentSession` (including unsaved drafts and clean external reloads). Embedded source nodes, `.py` cards and directories dispatch through the existing route path; focused scope navigation preserves secondary tab identity. Native Qt regression failed on unsaved-draft Forward; see uploaded v2.82 report.

- v2.83 **failed host qualification:** selected-page history authority, exact-page re-selection on provider replacement, same-tab source→source navigation using existing source session, invalid-draft refusal, and expanded headless/Qt coverage. The v2.83 regression mistakenly expected a deleted scope to remain navigable. The v2.84 fix explicitly rejects stale focus routes and centralizes source-owner preflight. Native v2.84 verification is still required.

## Test policy and refactor gates

1. **Edit loop:** use a focused existing test module or pattern with `python3 -m unittest discover -s tests -p 'test_v280*.py' -v`, expanding to affected neighboring suites as needed. No unnecessary native Qt launch for headless domain-only changes.
2. **Release gate:** `bash scripts/agent-verify.sh --headless` plus archive validation, repository guidance checks, Python-first and ProgramGraph publication gates; report the exact results. Never remove valuable tests just to shorten the run.
3. **Host promotion:** if GUI, Qt callbacks or integration were changed, collect `bash scripts/agent-verify.sh --native` evidence on WolfCat-Studio. Existing smoke catches unexpected Python tracebacks and missing stage markers. Native release candidates without host proof remain pending.
4. **Cleanup rule:** prove that a branch is unused or superseded using call-site inventory and tests, delete it in the same patch that consolidates the owner, and retain minimal migration paths only for real persisted data. No speculative framework or duplicate compatibility shim.

**Canonical authorities:** `SourceDocumentSession` owns text revisions, `ProgramGraph` owns executable visual documents, `python_lowering.py` qualifies Python generation and import, `python_edit.py` guards source publication, `GraphDescriptor` is read-only, Qt owns presentation, and `docs/agents/NEXT-TASKS.md` alone owns active task statuses.

- v2.84 **candidate:** single `resolve_source_session_route()` for live source revision/scope validation; removes duplicate preflight in cross-provider and same-provider navigation. Qt smoke covers invalid draft, valid-but-renamed historical scope (must refuse), and restored scope (must succeed). Six new headless source-owner/history invariants. Native Linux qualification pending.

## Repeated navigation failure root investigation (2026-11-02)

- The v2.82/v2.83 Linux failures were at the same forwarded focused history step, not independent random GUI failures. The v2.83 test restored `def before()` after navigating `def unsaved()` then expected a Forward to `unsaved`'s deleted scope to succeed. That contradicts `graph_routes.resolve_graph` and the documented invalid-history refusal policy.
- Previous attempts also suffered from Qt selected-page vs. global active-provider alias drift; v2.83 improved this, but tests failed to distinguish a real regression from correct stale-route rejection.
- **Rule:** retain history entries for missing scopes; refuse to navigate until the current authoritative source revision again contains that exact scope; never parse disk to bypass invalid/dirty source. Only after provider success may history/camera/tab commit.
- New architecture gate: both provider-transition navigation and same-provider source history run through `resolve_source_session_route`, a headless-testable source owner adapter. Avoid adding new authority or exception catch-all.

## v2.85 architecture-coherent delivery (native pending)

- Host v2.84 doctor passed 953 tests; recovery, document and ProgramGraph native subprocesses passed; integration completed all navigation assertions, then `timeout` exited 124 just after `committed-source-history`. Its end-of-test `w.close()` had uncommitted draft fixtures and no automation for the production unsaved-document question. The UI safety dialog is preserved. The native QA now proves both rejection and explicit confirmation with a deadline and emits `QT_STAGE integration-shutdown-discard-confirmation`. This remains a *hypothesis* about the timeout until v2.85 host evidence confirms it.
- Common text/config files: opt-in bounded UTF-8 preview in existing resource nodes. No generic editable text owner, active content, traversal, symlink following or hidden-file preview. Unsupported binary, oversized or invalid UTF-8 material refuses safely. `open_resource_node` toggles available read-only previews on ordinary open.
- Relationship overlay: considers only visible file cards, including children of *explicitly expanded* folders. `source_associations._parse_existing_source()` consolidates shared AST reading and selects live source-session text when open, including invalid drafts that suppress stale saved relations. Static local-sibling resolution and certainty/provenance labeling are unchanged. At most 72 Python sources per snapshot, no background index.
- Headless v2.85 regression tests include UTF-8 boundaries, sanitization, symlink/size refusal, nested resource relationships, current dirty revisions, and invalid syntax. Native integration checks previews, visible nested edges and teardown interaction.
- **Next after host PASS:** reduce root-tab compatibility branch duplication with view-session parity proof; plan bounded cross-directory associations only with explicit source-relative semantics, not speculative runtime imports.

## v2.86 release candidate — exact changes

- Native v2.85 report **has not** been submitted; its host qualification status is unknown. The most recent uploaded native failure evidence remains v2.84's integration timeout. Do not claim v2.85 or v2.86 native PASS from headless tests.
- `_open_navigation_route` now chooses the selected Qt source view, uses `_navigate_source_document_in_tab` for both established root and secondary source routes, and retains root anchors as compatibility destinations. Initial unbound source-root activation is handled by existing `_activate_source_view`, avoiding inline duplicated alias setters. The original root resource opening behavior is preserved.
- `local_python_literal_files` supports explicit forward child segments only with a passed `workspace_root`. Candidate targets still must already be visible resource files; directory symlink segments, parent traversal, dynamic expressions, absolute paths and overly long strings refuse. Standalone sibling-only use remains unchanged. The graph still caps scanned visible Python files at 72.
- Added 12 headless regression tests (root/secondary route policy, live invalid drafts, visible child evidence, dynamic/path/symlink refusals, nested explicit expansions), plus native Qt stages for root source file switching/history/refusal and child-path evidence. No generic file editor, AST owner or dependency index was added.
- **Promotion gate:** 976 headless tests, Python-first/ProgramGraph gates and manifest/archive pass on CI; native Qt pending WolfCat-Studio. Installer may prune old releases **only after** full native pass.

## v2.87 canvas revision owner repair (native pending)

- **Observed native failure:** `qualification-20261102-011456-38194.tar.gz` reported three `KeyError: resource-literal:...` callbacks in `NodeItem.resize_now → GraphCanvas.update_edges`. `GraphCanvas.rebuild()` validated one `resource_graph` while later callbacks retrieved a different selected tab's global `window.resource_graph`. This is a real renderer revision mismatch, not a test-only stale-scope expectation.
- **Single fix boundary:** `GraphCanvas` stores a non-owning reference `_render_graph` to its most recently validated graph projection. Nodes, nested surface metadata and edges derive from that reference and its `GraphDescriptor`; source and program port connection badges also read the canvas's descriptor. `validated_edge_payloads` rejects missing, extra or identity-changed edges instead of silently hiding mismatches. Stale card timers do not redraw cleared scenes; geometry refreshes defer until the scene is ready. No replacement graph store, source parser, or tab system.
- **Native regression:** `QT_STAGE resource-tab-render-revision-isolation` generates an evidenced relative-child resource edge, switches to the original resource tab, calls both delayed and explicit updates on the inactive canvas, and requires the original wire to remain intact. The full native Qt lifecycle and four subprocess markers must still pass on WolfCat-Studio.
- **Headless regression:** Eight new tests cover independent resource revisions, added/deleted/duplicate/mutated edges and source provenance. Pending Linux host PASS; do not declare v2.87 fully qualified from headless tests.

## v2.88 visible package import + relationship filter milestone (native pending)

- Extended **existing** `source_associations` static reader and `resource_graph.directory_graph`; did not add a provider/index, mutable graph owner, filesystem crawler or a package execution path. For dotted absolute imports, explicit root/expanded package folders and visible `__init__.py` evidence are required. For relative imports, only one dot and a package init qualify. Imports remain labeled `local-file-candidate`, declaration matches `syntactic-name-match`, and literal paths `literal-path-candidate`; runtime import resolution and dynamic expressions are not claimed.
- Each resource tab retains two presentation layer choices (`imports`, `references`) in its existing `ResourceTabView`. The existing overlay toggle remains; filter changes go through `browse_resource` and `resolve_graph`, so ports/edges/immutable graph contract remain in sync. No global filter applied across inactive tabs.
- Closed Python files use size-bounded nofollow regular-file reads with PEP-263 encoding detection, source session text overrides disk, invalid drafts suppress stale relationship edges. One screenshot/Qt stage `resource-relationship-layer-and-tab-isolation` exercises the menu and validated descriptor.
- **Host status:** v2.87 has no uploaded native report yet, so v2.81 is still the latest proven host-qualified baseline. Require all native stages, including v2.87's delayed edge refresh, and no Python callback tracebacks before cleanup/promotion.

## v2.89 relationship inspection milestone (native pending)

- Source of truth: the selected resource canvas's immutable `GraphDescriptor` and its exact `_render_graph` revision. `inspect_resource_relationship` validates the entire edge payload and checks endpoint node hashes, visible-file roots and symlink components before exposing a read-only inspection. Never read another tab's raw graph or parse a file to inspect a relationship.
- User flow: select/right-click an import or literal-reference edge to view bounded source-line evidence in the existing Inspector panel. Actions follow existing `Route`/`GraphViewSessions` policy; `.py` opens the source graph and non-Python targets open their enclosing resource directory. No generic editable file owner.
- Qt regression covers inspector evidence, inactive-tab refusal, endpoint route/history, and preservation of delayed inactive edge rendering. Headless tests cover mutated identities, changed edge revisions, symlink retargets and missing evidence.
- **Next:** on successful host qualification, consider precise source-line focusing tied to current live revisions, stronger selected-file framing and relationship filtering for larger explicitly visible workspaces; avoid eager repository scans and unproven runtime semantics.

## v2.90 exact evidence navigation milestone (native pending)

- The selected resource canvas still owns inspection evidence through its exact immutable contract. The existing source association AST reader now qualifies concrete Import/ImportFrom/Call source segments by exact starting line against the latest `SourceDocumentSession` text (bounded 512 KB); deleted/renamed/shifted/invalid source refuses before route/history mutation. Synthetic declaration-match annotations remain inspectable but not source-jumpable.
- Existing `Route`/`GraphViewSessions` and `QPlainTextEdit` own file navigation and cursor selection. After qualification, the same source owner is published once, avoiding duplicate recovery prompts; revision and identity are checked again after routing. Non-Python file endpoints now select/frame the existing file card in its parent resource graph instead of just opening a folder.
- Fourteen new headless tests and `QT_STAGE resource-evidence-line-and-file-framing` cover evidence preflight, exact line, stale draft, history, target selection and clean shutdown. Native Qt host qualification pending; v2.90 native report `qualification-20261102-021332-41511.tar.gz` now confirms a newer host pass.
- **Next:** after native confirmation, consider bounded selected-file relationship search and direct source-to-target graph navigation. Keep all new views projections, not alternate semantic owners.

## v2.91 focused resource relationships (native pending)

- Existing `directory_graph` relationship emission now optionally filters to one *already visible* file with `incoming`, `outgoing` or `both` orientation. It intersects with existing `imports` / `references` layers, never adds missing nodes, walks additional directories, follows symlinks, builds an index, or asserts runtime imports. Unrelated file cards remain visible.
- `ResourceTabView` retains the focus and direction alongside its established layer and expanded-path presentation preferences. The same `resolve_graph` provider constructs all revisions; root aliases reflect only the selected tab. Changing folders/pages resets focus after successful qualification, preserving navigation history and refusing stale focus routes instead of manufacturing a file.
- Context menus on file cards and inspected wires, plus the resource toolbar and Inspector, can focus a file or inspected endpoint. A successful rebuild clears stale Inspector actions; resource focus cannot cross inactive canvas revisions. Source-document revisions and graph semantic owners remain unchanged.
- Sixteen headless regressions test directional topology, static layers, current live text, visible assets, symlink/hidden/nonexistent paths, and graph-route contracts; Qt stage `resource-focused-file-neighborhood-and-tab-isolation` covers tab/camera/render revision behavior and toolbar states. Require full WolfCat-Studio native qualification before cleanup and promotion.
- **Next:** after host PASS, inspect usability, one-hop evidence search and on-screen relationship summaries. More ambitious repository-wide indexing or generic editors require separate contracts and bounded performance evidence; do not build early.

## v2.92 visible relationship explorer (native pending)

- `search_resource_relationships` searches only the selected resource graph's validated immutable `GraphDescriptor` and current read-only projection. A source statement, filename, edge kind, evidence path or certainty can match. Results are deterministic, case-insensitive and limited to 24 displayed rows by default, with a complete count. Query length capped at 128 characters. No filesystem discovery, full-repository index, source execution or new document owner.
- A single descriptor validation precedes searching; each candidate's raw node identity, visible root, current file existence and symlink status are independently qualified. This avoids repeated descriptor-wide validation for each result without weakening fail-closed conditions.
- Existing resource menu / file-card context menu opens the Inspector explorer. A file-card query starts with a one-hop focus and can walk two visible hops in either direction; clicking a result uses the existing relationship evidence Inspector and its qualified navigation actions. Callback guards capture the exact selected canvas and its render revision. Stale tabs or revisions cannot rebind a result to a newer edge with the same ID.
- Twenty-six new model regressions and `QT_STAGE resource-revisioned-relationship-explorer` check matching, type counts, visible focus, live drafts, missing targets, symlink swaps, graph revision changes, and Inspector interaction. Native Qt remains pending on WolfCat-Studio; do not promote based on headless testing.
- **Next:** prioritize deeper Python source ↔ visual graph reconciliation and further GUI dispatch consolidation; do not construct a second relationship engine or package-wide index before the current owner contracts are qualified.

## v2.93 Qt lifecycle and generated-source reconciliation review (native pending)

- Host v2.92 `qualification-20261102-024544-43211.tar.gz` passed doctor and reached the new relationship explorer. `qt_smoke.py` asserted one global `ResourceRelationshipResult` after replacing query contents; deferred `deleteLater()` leaves retired widgets attached until the event loop processes deferred deletes. This is not evidence of a Python relationship-provider failure. Fix at the UI lifetime boundary by detaching removed Inspector controls synchronously, including stale result-panel children. The Qt smoke scopes result enumeration to the active panel, tests immediate retirement and uses exact panel+render/canvas checks on result actions. Require host test before claiming resolved.
- `review_generated_source_edit()` and `LinkedPythonSource.review_edits()` now return immutable, function/node-identified proposed literal/operator changes using the exact compiler qualification and one revision/conflict gate also used by `import_edits()`. Review is read-only. Import requalifies immediately before one atomic graph transaction; source text, trivia, unknown statements, disk versions and undo history are preserved on refusal. No source-region reverse parser or secondary authority was created. New ProgramGraph `Review open .py` uses this preflight. Added 12 headless cases and native Qt review stage.
- **Next:** host-qualify first; then target function-level mapping of independently authored source and safe conflict UI with stable anchors. Do not claim arbitrary Python ↔ graph editing from this restricted generated-source preflight. Preserve v2.90 if host fails.

- **Host baseline correction (2026-11-02):** Independently checked the previously uploaded `qualification-20261102-021332-41511.tar.gz`: its Qt integration reaches `resource-evidence-line-and-file-framing` and ends in `NATIVE_QT_SMOKE_PASS`. Therefore **v2.90**, not v2.88, is the newest confirmed Linux-qualified baseline. Earlier statements that the v2.90 report was not received are historical/outdated.

## v2.94 root-compatibility identity and independent source function milestone (native pending)

- Uploaded v2.93 report `qualification-20261102-032306-45967.tar.gz` passed doctor and the relationship-explorer assertions, then failed with `KeyError: resource` at the next test. Fixture cleanup had called `_close_graph_tab(currentIndex)` twice; Qt selected the original resource root after the first close. Production code previously guarded only `len(resource_tabs)==1`, allowing the root to be deleted when other resource views existed. Both original root session IDs now have explicit close refusal, independent of tab count. Qt smoke closes exact fixture pages by identity and verifies the preserved root with secondary views present. Never hide this failure with dict.get fallback.
- The first independently authored Python reconciliation slice selects **one named top-level function** from an existing `SourceDocumentSession`, allowing unrelated imports/functions to remain in that same file. No new parser or editor: the Python AST is used only for bounded source-region selection, while `_qualified_source_edit_plan` proves all proposed node changes by full re-lowering of a synthetic candidate in which only the chosen function differs. The synthetic source is never published. Reviews carry graph revision, source revision and SHA-256; an explicit import requalifies and commits a single `ProgramGraph.edit_many` transaction. All other source code remains untouched, visible in its text owner, and NOT represented by the graph. Unsupported functions, duplicates, stale sessions and external changes are refused. UI actions are `Review independent .py function` and `Import reviewed function` in the existing Function… menu, separate from exact generated-source linking.
- **Next:** native qualification, then source-region identity improvements for rename/reorder and precise conflict descriptions, followed by GUI/root-tab migration audit. This is *not* arbitrary Python↔graph round-trip or an implicit source link.

- **v2.95 candidate:** A single independently authored `.py` may now contribute several **explicitly selected** graph-owned functions to one read-only preflight and one atomic import. Unselected source remains opaque. Tests cover input ordering, source-only code, multiple edits, stale revisions, ambiguous names, unsupported syntax, and native GUI integration. The v2.94 root-tab fix is carried forward; host must still qualify native Qt before promotion.

## Efficient development cadence (v2.95)

Use the repository's focused `unittest discover -p ...` against an actual affected subsystem as the inner loop, reuse `python_lowering._qualified_source_edit_plan` instead of creating another importer, then run `scripts/agent-verify.sh --headless` **once after feature, tests, docs and release metadata are finalized**. Use `scripts/build_release.py` to package final bytes and run `install_linux.py --headless` in an isolated `$HOME` once. Never trade away the native Qt host gate or old-install preservation for speed. Don't manufacture new patch versions to fix errors in tests when the expected behavior was invalid.

## Native CI without extra Qt application code

The existing `.github/workflows/headless.yml` now adds a separate `native-qt` job using Ubuntu's system `python3-pyqt6`. It runs `scripts/agent-verify.sh --native` and uploads on-failure Qt logs/screenshots. This is an **early regression gate** before the user installs a ZIP; it is not a claim about the user's Mint/Qt desktop and does not promote or clean versions on that machine. The headless job remains independent and fast.

## v2.96 compiler-proven comparison changes and diagnostic proof (native pending)

- Qualified typed integer comparison substitutions `<` / `==` with identical known node port schemas, full trial graph lowering, and one atomic import. Graph/source identities, edge layout, source buffers, disk saves and undo semantics are unchanged.
- Failed independent multi-function batches identify the first refusing selected function and original source-line region by retrying `_qualified_source_edit_plan` on individual regions **only after full-batch failure**. No partial approval or graph mutation.
- Current gate: `test_v296_comparison_reconciliation.py`, full headless doctor/ProgramGraph/Python qualification, archive integrity and isolated install. Require WolfCat-Studio Qt qualification before promotion.

## v2.97 typed integer comparison family (native pending)

- Added `>`, `>=`, `<=`, `!=` ProgramGraph operations with identical canonical `py:int` inputs and `py:bool` output, using the existing `NODE_TEMPLATES` owner and `replace_node_operation` validation.
- `python_lowering.INTEGER_COMPARISON_AST` now supplies all six Python comparison AST nodes for graph lowering **and** both generated/independent source reconciliation. Source modifications still require complete AST or byte-exact compiler proof and one atomic graph transaction.
- Independent source parse failure reports its actual line and column; no synthetic function evidence is claimed before parse success. Added adversarial typed/cross-branch/runtime, round-trip, undo/redo and source-owner tests. No new importer or graph cache.
- Host gate: all existing native Qt stages and new operation creation interactions must pass on WolfCat-Studio before promotion. Latest confirmed baseline remains v2.90 until a new host report is supplied.

## v2.98 Qt cumulative-test root cause and source line receipts (native pending)

- Host v2.97 `qualification-20261102-041636-47889.tar.gz` passed Python doctor and reached `QT_STAGE program-independent-function-review-and-import`, then failed asserting `len(receipt.changes)==1`. Actual graph literal at this point was `24`; the native smoke tried `replace('_smi_value_0 = 25', '_smi_value_0 = 31')`, a **silent no-op**. Compiler correctly reported no changes. The test also failed to restore the changed graph after its independent-source edit, threatening later linked-source stages. Both are test lifecycle faults, not a reason to change valid compiler behavior.
- All program-smoke textual substitutions now verify an exact single existing occurrence and a nonempty change; the independent edit is synthesized from `preview_python().node_lines` and the current numeric AST literal. After testing independent-source undo/redo it restores the original graph before linked-source scenarios. `test_v298_native_reconciliation_fixture.py` reproduces the historical baseline, proof, restore, next linked edit, and source preservation without PyQt. Do not convert no-op preflight into a one-edit claim. The native smoke also contained two invalid `assert roundtrip.undo()` expressions: the `ProgramWorkspace.undo()` Qt handler returns `None` and the actual `ProgramGraph.undo()` result is internal. Both were replaced by commands followed by authoritative graph-state assertions. Headless native-smoke-contract tests prohibit those invalid assertions and unguarded source substitutions.
- Independent function review now carries optional `(function, node_id, original_source_line)` evidence for exact, uniquely named assignment targets, after the existing full AST trial-compiler proof. The evidence is ephemeral and advisory. It is never a stable persistent mapping or an authorization token; import rechecks source SHA/revision, graph revision and complete compiler equivalence. GUI displays these original source-owner lines when available. Edited parameter names, argument kinds/defaults, annotations or return annotations are refused at the original source function line; this is diagnostics, not new support for signature edits.
- **Next:** require WolfCat-Studio native Qt PASS on the entire suite before promotion. Then prioritize stable per-function semantics/conflict reporting and root-tab compatibility consolidation, not more unproven mappings or separate document owners.

## v2.99 full integer arithmetic and exact function identity (native pending)

- v2.98 host `qualification-20261102-044314-48735.tar.gz` passed complete doctor/native Qt through the integration shutdown and becomes the new verified rollback baseline.
- Added Python integer floor division/modulo through existing graph operation schemas and compiler-owned `INTEGER_ARITHMETIC_AST`, reused for generated and independent source review/import. Fixed negative integer literals to be recognized in parsed Python as a bounded unary-minus constant; never evaluate arbitrary AST or import unsupported Python.
- Source function identity errors report exact missing top-level names or duplicate original lines, without automatic rename or altering source ownership. Headless regression tests exercise signed division/modulo, zero-division, source exactness, atomic batch edits, source-line evidence and undo/redo.
- Next: host-qualify v2.99, then review source-region correspondence/conflict UX and root-tab compatibility consolidation, preserving the existing source/graph/view authorities.

## v2.100 independent source correspondence (native pending)

- Native v2.99 evidence has not been supplied. Most recent confirmed host gate remains v2.98 `qualification-20261102-044314-48735.tar.gz`.
- Bounded module-scope binding guard refuses selected function names explicitly shadowed by other binding constructs, including module compound suites and walrus expressions from comprehensions. Local definitions and comprehension iterator targets remain out of scope. Dynamic Python rebinding is not statically solved; do not claim runtime proof.
- Original-source statement spans are ephemeral Unicode-column evidence for uniquely matched AST targets, not a source-to-graph owner or an authorization token. Full trial compilation, graph/source revision and SHA checks precede one atomic import. UI displays the spans in the existing Function menu review.
- Release version coherence is now tested against the README shell invocation and packaged install script; installed versions are sorted numerically, so `v2.101` does not sort before `v2.12`. Next: qualify native Qt, then improve supported source-region edit semantics only where compiler proof can remain complete.

## v2.101 compiler-proven input-wire changes (host-qualified)

- Source reconciliation now proposes `ProgramGraph.replace_input` for a qualified arithmetic/comparison expression operand referring to another **unique, existing source-generated value in the same graph function**. This is not a generic AST importer: no source-defined graph nodes are synthesized and no code is executed.
- Reviews report old/new graph producer IDs and output pin IDs. An explicit import requalifies the edited source and complete resulting graph; orphans, unsupported expressions, stale source or graph revisions, unknown values, type or control differences refuse the whole batch. No automatic source writes or partial commits.
- Generated source, independently authored selected functions, combined literal/operator/input changes, atomic undo/redo, exact source evidence and negative cases have new headless regressions. Native Qt promotion remains required on WolfCat-Studio; latest confirmed host version v2.98.
- Next: host qualification, then refine stable source-region conflicts and identify obsolete workbench root aliases for safe consolidation.

## v2.102 existing-value input reconciliation (host-qualified)

- Host v2.101 report `qualification-20261102-052934-51512.tar.gz` completes all Qt stages through `NATIVE_QT_SMOKE_PASS`; v2.101 becomes the verified rollback baseline.
- Extended the same `python_lowering._qualified_source_edit_plan` and graph-owned `replace_input` transaction to qualified existing ports on `python.not`, `python.select_int`, `python.select_bool`, `python.call`, `python.return` and `python.return_flow`. All source values must identify unique existing same-function generated producers with compatible ports; pure call targets are checked against the current graph-owned callee signature. No new AST-to-graph importer, second function mapping, or implicit source write.
- Source-only trivia mode aligns Return statements by exact structural ordering, then still requires trial-graph AST equivalence. Generated edits require byte-exact text equivalence. Orphan-producing rewires, control changes, effects, changed emitted statement ordering, unavailable or ambiguous values refuse the full transaction. Reviews are advisory and imports revalidate source/graph revision and SHA.
- `tests/test_v2102_semantic_input_reconciliation.py` tests original source preservation, selection and Boolean rewires, flow Return, pure call arguments, independent source comments, atomic undo, and negative control/orphan edits. This change is headless-tested; native Qt qualification on WolfCat-Studio is mandatory before release promotion.
- **Next:** improve specific conflict diagnostics for rewires whose generated statement order changes, without weakening proof; audit remaining root-tab aliases only behind a native parity suite.

## v2.103 pure dependency-order proof (native pending)

- The v2.102 WolfCat-Studio report (`qualification-20261102-060149-52354.tar.gz`) passes the full native Qt suite and `NATIVE_QT_SMOKE_PASS`, establishing the latest rollback baseline.
- Independent-source review/import may now reconcile graph input rewires that legitimately reorder **contiguous pure** `_smi_value_*` assignments. Existing graph node-line receipts align regenerated variable names with original graph nodes; assignments match by top-level function and generated target instead of incidental line position. No persistent mapping, new importer or source text mutation is introduced.
- Order equivalence explicitly refuses forward reference, duplicate identities, call side effects, potentially raising floor division/modulo, changed control blocks, and anything outside the compiler-proven pure run. Generated-source dialog imports remain byte exact. Atomic graph transactions and source SHA/revision checks are unchanged.
- Qualification: focused `test_v2103_pure_order_reconciliation.py`, full headless gate, integrity-checked release and isolated installer; new release still requires the full WolfCat-Studio native gate before install promotion.

## v2.104 branch-local pure dependency reconciliation and qualified packaging (native pending)

- Suite-local pure AST proof extends existing v2.103 restricted generated-value
  ordering inside each if/else, nested branch and for/while body independently.
  No cross-branch move, call/effect reordering, forward read, duplicate
  generated target, arbitrary AST reconstruction, or new document owner.
  Generated-source imports retain byte-exact proof.
- Real ProgramGraph branch fixture verifies independent-source review,
  existing-wire import, source-byte preservation, atomic undo/redo, strict
  linked-source refusal and invalid forward-reference refusal.
- Existing deterministic release builder gains an opt-in `--qualify-headless`
  that calls `scripts/agent-verify.sh --headless` before publication, with
  fail-closed tests. It is **not** a replacement for the WolfCat-Studio native
  Qt gate, safe cleanup and launch workflow.
- Next: qualify native Qt v2.104; extend correspondences only when a real
  graph/source compiler example proves semantics, and audit root compatibility
  branches with host parity coverage rather than speculative removals.

## v2.105 compiler-proven control and effectful call inputs (native pending)

- Existing Branch and Require condition data pins can be reconciled from Python
  through the current ProgramGraph.replace_input and compiler trial. Branch
  requires an existing two-arm If; Require requires the canonical fail-closed
  `if not ...: raise` guard. No execution-wire changes are admitted.
- Ordered `python.call_exec` argument changes can select another existing
  same-function producer without changing the call's execution pin, position,
  callee, or return-value contract. The full trial refuses changes that would
  move arguments across an effect or lose a graph node.
- Independent-source reviews expose original expression spans for Branch and
  Require condition replacements. These locations are advisory and are
  recomputed on every import; no new mapping authority exists.
- New bounded regressions exercise generated and independent source, combined
  control rewires, effectful calls, exact source spans, invalid effects, stale
  graph/source revisions, and atomic undo/redo.
- Pending gate: Linux Qt smoke on WolfCat-Studio. The last confirmed host
  baseline remains v2.102; no v2.104 host report has been supplied here.

## v2.106 execution-owned data-input reconciliation (native pending)

- Extended existing `SOURCE_REWIRE_OPERATIONS` and AST source-operand qualification to Bind (int/bool), mutable Local/Assign (int/bool), and bounded Repeat count. No new node, document owner, parser, or execution-flow editor.
- Repeat count uses its preceding uniquely named `_smi_repeat_count_N` assignment and the graph-owned For source-line receipt. Full trial graph re-lowering preserves single evaluation, range guard, and loop body; source modifications to any of those effects refuse the transaction.
- Read-only independent source receipts identify the exact RHS expression and correctly distinguish repeated writes to an existing slot via its compiler-proven occurrence index. They remain advisory and are regenerated at commit.
- Regressions cover byte-exact generated imports, independently authored source preservation, atomic two-write changes, bool binding, typed/wrong-count safety, stale revisions, and undo/redo. Host-native Qt qualification is still required before cleanup and automatic GUI launch.
- Next: review function-region correspondence and performance; consider fully proven additional execution/structural changes only if the compiler can preserve semantic equivalence. Keep root-tab compatibility removal behind native parity evidence.

## v2.107 compiler refusal diagnostics and baseline parsing (native pending)

- Rejected source edits now carry a bounded first-mismatch AST path, parsed
  candidate line, and syntax shape/value evidence where the existing compiler
  determines the edit cannot be reproduced. This is diagnostic information
  only, not a new parser, implicit rename policy, or acceptance rule.
- Independent-source batch rejection retains the original function name and
  actual source-owner region; the AST candidate is synthetic, so its line
  cannot be represented as a real source file address. Successful imports
  retain exact same revision/graph proof, source preservation and undo.
- Single-parses the already validated generated baseline within a source
  preflight instead of reparsing it for each mapping/proof stage.
- Headless regression suite: `tests/test_v2107_reconciliation_diagnostics.py`
  and existing v2.103–v2.106 source/graph suites. Native Qt and installation
  reports remain required before promoting this release.

## v2.108 source-receipt correctness and expression-scoped review (native pending)

- Repaired `_independent_change_lines` leaking the final selected function's
  assignment occurrence index to preceding function regions. Indices and
  repeated state-write receipts are now scoped to each authoritative function.
- Qualified review source spans now identify the exact changed expression for
  typed input wires (arithmetic/comparison operands, Boolean Not and Select,
  existing calls, Return value and previous state/Repeat cases). Changed
  literal/operator receipts select the RHS rather than the assignment target.
  A byte-offset to Unicode-column conversion remains confined to advisory
  evidence, and unknown/ambiguous AST mappings still omit their span.
- Headless regression fixtures cover multiple functions with different
  repeated targets, selection conditions, comparison/arith operands, ordered
  call arguments, structured Return, Unicode source and ambiguous target
  omissions. Reuses `ProgramGraph`, `SourceDocumentSession` and the existing
  full-trial Python compiler. No new editable source map or second authority.
- Last host-qualified baseline remains v2.102. v2.108 must pass the complete
  WolfCat-Studio native Qt gate before cleanup and launch promotion.

## v2.109 definition-time source identity and bounded preflight (native pending)

- Explicit selected-function module bindings are now checked across the
  definition-time expressions evaluated by other top-level function/class
  definitions (defaults, decorators, annotations, class bases/keywords and
  lambda defaults), plus explicit class-suite `global` writes. Neither delayed
  function/lambda bodies nor class-local stores are mistaken for module writes.
  This is a conservative static guard, not dynamic execution analysis.
- Failed multi-function preflights skip unchanged selected regions during
  individual compiler diagnostics, avoiding repeated whole-graph recompilation
  for those functions. Full combined graph/compiler proof and one atomic import
  are still required for acceptance; no partial import is authorized.
- Read-only statement receipt projection now gathers assignment/If/For/Return
  witnesses from one AST pass per owner; ambiguity still suppresses evidence.
- Focused regressions use actual graph and source owners, verify refusal and
  no mutation, positive local-binding preservation and bounded diagnostic calls.
  Latest independently host-qualified version remains v2.102.

## v2.110 source identity batch and receipt cleanup (native pending)

- One explicit selected-function map is checked against the module AST in a
  **single traversal**, replacing the previous O(selected-functions × module)
  identity scan. The exact function AST object is still required; names do not
  imply fuzzy matching or cross-file ownership. Missing, duplicated, async or
  incompatible signatures remain refused before the shared binding check.
- Declaration-only module annotations are allowed because they do not bind a
  value; initialized annotations, annotation expressions with explicit named
  writes, decorators, imports, compound statements, and class-body `global`
  writes are still checked conservatively. Deferred function/class locals do
  not create fake module conflicts.
- Eliminated the duplicate Return AST walk in independent source receipt
  indexing; original evidence and per-function ordinal ownership remain.
- Headless contracts: `tests/test_v2110_module_identity_batch.py`,
  `tests/test_v2109_module_definition_binding.py`, and all prior source
  import/undo safety gates. Native Qt on WolfCat-Studio still required.

## v2.111 — class-global identity and top-level indexing (native pending)

- Compiler review now rejects explicit global writes made from class suites,
  including nested class bodies, imports, function/class definitions, exception
  aliases, and pattern captures. Class-local names and comprehension targets
  do not shadow module functions. Never scan deferred method bodies as if they
  execute during class definition.
- Source and graph baseline top-level function definitions are indexed once for
  the entire selection. Reconciliation still requires exact names/signatures,
  one module identity scan, full trial compilation, and one undoable commit.
- Native Qt on WolfCat-Studio remains pending; v2.102 is still the latest
  independently evidenced host-qualified baseline.
- Tests: `tests/test_v2111_function_scope_identity.py` and older v2.109/v2.110
  identity contracts. **Next:** source/graph structural correspondence where
  semantic proof permits, plus evidenced root-tab compatibility removal.

## v2.112 — shared proof reuse and inline release handoff (native pending)

- Independent function review computes a canonical `PythonPreview` and parses the source-owned and graph-generated ASTs once per batch. Its internal full compiler proof and optional per-region diagnostics now reuse those exact synchronous, revision-checked witnesses. No preflight state persists or acts as permission to commit; explicit import still recomputes and validates all owners.
- The compiler plan uses one defensive graph state snapshot after revision validation; the trial graph remains independent. Reconciliation candidate statements are collected in one AST traversal for literals, operators, assignments, returns, branch/require conditions and bounded loops. Existing per-function repeat-count witnesses remain scope-specific. Final graph trial compilation, effect guards and source digest/revision gates are unchanged.
- User handoff now distributes one ZIP and an inline pasteable Bash block. `install_linux.py` remains the single authority for archive validation, native qualification, safe cleanup and installed shortcut. The Bash wrapper chooses only reports created during this invocation, extracts them and launches the verified app; no separate downloaded `.sh` artifact required. Keep the bundled historical `INSTALL-AND-REPORT.sh` until compatibility removal has native parity evidence.
- Tests: `test_v2112_shared_preflight.py` and release-consistency checks; complete headless and WolfCat-Studio native Qt gates remain mandatory. Latest host qualified baseline is still v2.102.


## v2.114 — named-call source proof and receipt precision (native pending)

- Existing `python.call` and `python.call_exec` input rewires can be reviewed from **explicitly selected, independently authored** Python functions written using exact keyword names or positional-prefix-plus-keyword calls. The normalized candidate is a deep copy of selected AST regions; source bytes, Unicode positions and keyword order remain owned by `SourceDocumentSession` and are never rewritten.
- Keyword target qualification reuses the single source module identity traversal. A non-selected target must have an unchanged AST-equivalent graph-owned definition; a selected target must pass the existing signature and combined whole-graph proof. Explicit local-name operands only; no star/unpacking, literals or effectful argument expressions, ambiguous/unknown keywords or default-argument imports. Canonical output remains positional and trial compiler proof remains mandatory.
- Original-source receipts now locate the exact keyword *value* span, not the call or assignment line. Generated-source dialogue still requires byte-exact reproduction; only the independent-source proof allows this syntax normalization. Imports recompute source digest, revisions and compiler proof and commit one transaction, never a partial set.
- New tests: `tests/test_v2113_keyword_call_reconciliation.py` plus existing input, ordered-effect and source ownership suites. **Host Qt promotion is pending**; latest independently recorded native-qualified version remains v2.102.

## v2.114 — independent local correspondence and source-only trivia (native pending)

- An explicitly selected independently authored function can spell a uniquely assigned `_smi_value_N` temporary with an unambiguous local alias. It can also include a leading function docstring and direct-body `pass` statements. The only normalization is on a copied AST inside `python_lowering._independent_functions_plan` prior to the **same full compiler proof**; the source file is not rewritten.
- Fail closed on moved/duplicate assignments, alias collisions with parameters/callees/generated names, nested scopes, global/nonlocal bindings, unsupported AST, stale source revisions, and synthetic node creation. The existing linked generated-source dialog remains byte-exact. Docs and passes are source-only; graph publication does not reproduce Python `__doc__` metadata.
- Regression: `tests/test_v2114_independent_local_correspondence.py`, existing v2.113 keyword/call and v2.95–v2.112 reconciliation suites. Headless and native Qt host gates are separate. Last confirmed native baseline remains v2.102.

## v2.115 — original-source local syntax and source receipts (native pending)

- Host v2.114 report `qualification-20261102-103613-64130.tar.gz` completes native Qt smoke with `NATIVE_QT_SMOKE_PASS`, including shutdown; v2.114 is the verified rollback baseline.
- The **existing independent function proof** (not linked/generated source import) may temporarily normalize a local typed assignment with a simple built-in annotation (`int`, `bool`, `str`) into an ordinary assignment. Source-owned annotations remain intact on disk/in the open session. Complex annotation expressions, attributes/subscript targets and declarations without values refuse the full trial proof.
- Remove `pass` only from a direct function body or a populated `if`, `else`, `for`, `while` suite in the transient trial AST. Do not remove the only statement of an empty suite, alter control flow, or create a new AST/graph authority.
- Read-only source receipts identify annotated assignment RHS and keyword argument input spans; tests cover one-transaction import, undo and source preservation, nested suite trivia, unsupported annotation and empty-suite refusal.
- Next: host native Qt qualification, then prioritize broader independently authored code correspondence, shared compiler contract cleanup, and evidence-based root-tab retirement.

## v2.116 — order-independent unique local identity (native pending)

- Host report `qualification-20261102-104724-64648.tar.gz` confirms v2.115 completed native Qt with `NATIVE_QT_SMOKE_PASS`, through integration shutdown. It is now the verified baseline.
- An independently authored selected function may rename **one uniquely assigned generated temporary** while pure compiler-generated statements are reordered to satisfy a different dependency, including in structured branches. Candidate matching is by exactly one missing generated binding plus one newly introduced local; it never uses fuzzy similarity. Multi-alias positional matching is disabled where unchanged generated names were themselves reordered.
- Composes with existing simple local annotations, no-op `pass`, independent function source ownership, trial graph compiler proof, all-or-nothing undoable imports, revision/digest checks, and strict linked generated-source import. Other unsupported reorderings still fail closed.
- Test fixtures: `tests/test_v2116_structural_local_identity.py` plus v2.103/v2.104/v2.114/v2.115 and release consistency gates. Next: host-qualify v2.116, then consider broader structural matching only when compiler proof supplies a unique identity and corresponding source region.

## v2.117 — multi-identity compiler proof and bounded release doctor (native pending)

- Independently authored Python can rename several graph-generated pure locals when their defining AST expressions uniquely identify the original producer, with dependency aliases resolved first. Ambiguous, repeated, effectful or potentially raising producers never gain inferred identity. Compiler re-lowering, graph validation, one undoable transaction and source revision/digest checks remain authoritative.
- A safe pure statement reorder with **no** graph changes is a source-owned no-op, not an import failure; the generated-source workflow remains strictly ordered.
- `RUN-ALL.sh` now bounds the full `doctor.sh` run with `SMI_DOCTOR_TIMEOUT` (default 240s), preserves the existing report archive and explicitly marks timeout failure. The native Qt runner already has a separate timeout. No second qualification pipeline was added.
- Tests: `test_v2117_multi_alias_proof.py`, `test_v2117_qualification_watchdog.py`, and adjacent 2116/2104/2114/2103 suites. Next: host-qualify v2.117 before promotion, then continue existing compiler/reconciliation and view-session consolidation work.

## v2.118 — bounded integer expression proof (native pending)

- Added constant-only integer arithmetic normalization **inside the existing independent-source proof function**. Only bounded, pure, built-in integer operations with statically known, nonzero divisors fold. Expression syntax remains owned by SourceDocumentSession; graph literals can change only through the existing compiler-proven `set_property` transaction. No expression nodes are synthesized and no AST is evaluated with `eval` or executed.
- The v2.118 regression suite proves signed `//` and `%` behavior, nested arithmetic, source-only equivalents, annotated/readable locals, unmodeled docstrings, exact source spans, graph undo/redo, external source conflicts, stale graph revisions and refusal of unknown/effectful/raising/oversized values. The generated-source importer is intentionally unchanged.
- Next: host native Qt qualification, then continue structural independent function correspondence and carefully characterize/delete legacy UI compatibility only after behavior parity; don't build a second source-to-graph importer.

- Additional v2.118 Boolean proof: exact bounded integer comparisons and all-fixed Boolean `not`/`and`/`or` may normalize a transient candidate for an existing Boolean literal. No dynamic/chained comparator, call or mixed-type coercion is admitted; generated-source editing stays strict. `test_v2118_boolean_expression_proof.py` provides 3 targeted scenarios plus refusal subcases.

## v2.119 — conditional literal proof and release supervisor (native pending)

- Independently authored selected function candidates may normalize literal-only `if` expressions when the condition is an exact Boolean and **both** branches are already exact `py:int` or `py:bool` constants of the same type; integer values must stay within signed 63-bit magnitude. No short-circuit deletion of unknown, dynamic, effectful or raising branches; no string, floating or alternate graph owner. Transient AST is bounded at 4096 nodes. Source text remains untouched; trial graph compiler and source/graph revision checks still authorize all edits.
- `RUN-ALL.sh` writes `qualification-verdict.txt` into the archive before finishing, and `install_linux.run_qualification` supervises the entire private process group with a configurable bounded timeout (default 520 seconds). Timed-out child trees are terminated; native promotion, old-version pruning and launch remain forbidden. An archived verdict improves diagnosis but does not override a nonzero exit code.
- Tests `test_v2119_source_constant_proof.py`, `test_v2119_release_supervision.py`, historical v2.118 constant proof suites, native/installer regression suites, full headless and WolfCat-Studio Qt gates. Next: host qualification, then broader *compiler-proven* function correspondence and evidence-based root-tab retirement, not syntax-only exception accumulation.

## v2.120 — source-only local annotation and no-op guard proof (native pending)

- A pre-existing assigned local or function parameter may have a bare
  built-in annotation (`int`, `bool`, `str`) in the independently authored
  function. The proof AST ignores it; the source editor still owns it.
- Conditional guards whose condition is an **exact constant Boolean** and
  whose arms are all `pass` may be normalized away when other statements
  remain. No dynamic, truthy-integer or effectful guard is erased. Do not
  erase an entire control suite merely because its children are no-ops.
- Existing graph trial-lowering, source revision/digest, atomic import, undo
  and generated-source strictness are unchanged. Tests cover combined
  keyword-call rewires, readable locals, branch-local cases and refusals.
- v2.120 later passed host headless and native Qt checks; v2.121 requires a fresh native qualification.

## v2.122 — root-source navigation refusal is one transaction (native pending)

- The **existing** source-tab navigation path accepts a private `root_anchor` target for the already-open protected source root. It runs the same source-session, live-revision, and scope proof while the filesystem root remains selected, committing the Qt page switch only after proof. Failed invalid/deleted focus stays on the resource tab and never advances either view history. The never-opened root still uses the existing source opening adapter so invalid Python remains inspectable in the text editor.
- `_transition_graph_tab` now verifies selected Qt page membership before changing tab registries, aliases, cameras, or history. No new route session, parser, graph owner or compatibility storage was added.
- Tests: four new headless regressions and existing route/history tests; native Qt stage `protected-root-source-refusal-atomicity` covers real page identity, aliases, refusal and success. v2.121 CI passed, v2.120 is last uploaded native Linux Mint report. **Do not claim v2.122 host PASS until a report is received.**
- Next: after native success, characterize and prune the remaining duplicated root/secondary dispatch and camera handling. Avoid deleting root anchors while the original file picker or persisted view modes require them.

## v2.123 — independent-source proof stage consolidation (host native pending)

- Extracted the existing temporary source-AST preparation, generated-local
  identity correspondence and keyword-call normalization into explicit private
  helpers **within** `python_lowering.py`. The batch planner still owns module
  selection and one full-graph compiler preflight, including guarded atomic
  imports and selected-function-only diagnostic retries. The original source
  text, AST and document session remain immutable during read-only review.
- Added targeted refusal/non-mutation characterization (ambiguous equal
  producers, nested scope bindings, unqualified keyword expressions, large
  AST) without expanding supported Python syntax. Existing multi-function
  atomic, conflicts, graph undo, and source-preservation tests remain gates.
- Host v2.122 is not yet separately qualified despite GitHub's two passing
  jobs. v2.123 has no native host evidence; **do not** promote until its full
  report passes. Next Qt cleanup remains gated on root-route native parity.

## v2.124 — independent batch diagnostic retry gate (host native pending)

- In `_independent_functions_plan`, failed full-batch proof attribution now skips
  functions whose **transient normalized candidate** matches the already-indexed
  graph-generated baseline. The previous check compared *authored source AST*
  and retried docstrings, `pass`, annotations and keyword-call spelling that
  cannot independently explain a compiler refusal. No additional compiler
  authority, source rewrite, persisted map or graph edit is introduced.
- Real semantic changes still get an isolated retry against the same baseline
  and original source-region span. Combined failures are still atomic refusals.
- Three adversarial regression tests count full-proof and changed-region retries,
  confirm original document/graph revisions remain unchanged and keep failed
  region attribution precise. No Qt production behavior was altered.
- The new upload `qualification-20261108-125446-79635.tar.gz` is a verified
  **v2.121** host report (1,338 headless tests, native Qt PASS); do not mistake
  it for v2.122 or v2.123. v2.124 host qualification remains pending.
