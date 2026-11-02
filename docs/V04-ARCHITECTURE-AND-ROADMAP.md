# V0.4 architecture decision and handoff

## Baseline and ownership

Authoritative prototype source: `studio_native/python_graph.py` (read-only AST/symtable projection); `studio_native/python_edit.py` (bounded reviewed source edits); `studio_native/model.py` (node-builder presentation draft); `studio_native/gui.py` (one shared native Qt scene/node renderer). This does **not** supplant the separately maintained Superior MI Studio `semantics.py`/`sessions.py` authorities. Do not merge this prototype's presentation format into production as a semantic format.

## Approved design directions, reflected in the implemented pilot

1. **Whole file is a presentation, not a new graph.** Stable IDs of declarations and operations in the focused scope are reused. Whole file arranges scopes into separate compact lanes with breadcrumb labels (not infinitely nested visual frames), allowing independent collapse of branches of the scope tree; drilldown remains as Focus. Scope frames are containment, not execution wires. No new writes or additional graph documents occur on expansion/collapse.
2. **Presentation density is semantic.** Compact getters/literals/operators/control nodes share `NodeItem` and `PortItem` with full container-based nodes. Avoid duplicated renderer classes and arbitrary decorators per language.
3. **Execution and data are different.** Control edges appear white with triangular execution ports. Scalar/data ports remain colored circles; call and reference edges have distinct link metadata. `relation=reference` never means input evaluation or sequential execution.
4. **A whole-file dependency crosses scope boundaries only with a proven symbol source.** Anonymous/dynamic/ambiguous destinations remain unlinked and visible, not guessed. Module reads used only inside nested functions are qualified `indirect` dependencies; no fake direct function parameter.
5. **Do not collapse language semantics to a common visual icon.** Python `and/or` return operands and short-circuit; comparison chains evaluate in order. Both remain source-backed until their evaluation contract is qualified. Python type annotations are not treated as runtime data inputs by default; versions and definition-time behavior require separate analysis.
6. **Control graph is conservative.** Simple `if`/`elif`/`else` branches, straight-line assigns/returns, and path joins are projected. A source-backed operation/effect breaks inferred control successors. Branch-dependent values are rendered as *non-executable* value-merge projections, and are derived only when all reachable branches produce explicit known inputs. No visual source rewiring yet.
7. **Inline unconnected values are approved as a UX target, not yet wired as source edits.** Default vs literal vs uninitialized vs connected must be distinct in semantic contracts. A source-program input must never acquire a silent default because a Qt widget happens to exist.
8. **File-backed authoring remains guarded.** The `.py` file owns the program. Qt moves/expansions do not modify it. Existing literal/operand edits require syntax validation, hash comparison, reviewed diff, and a backup; unsupported edits refuse. Visual rewiring is a future language-specific source transformation, not a raw edge JSON mutation.

## Semantic contract to stabilize before broadening language support

| Layer | Stable independent concept | Future fields needed |
| --- | --- | --- |
| Scope | ownership, parent, language | symbol visibility, lifetime, phase, namespace |
| Symbol/Binding | identity, declaration site, reads/writes | aliasing, mutability, capture, global/nonlocal |
| Typed port | id, direction, relation, type | cardinality, optionality, default/wired binding, ownership, qualifiers |
| Operation | source expression/statement identity | purity, effects, exceptions, short circuit, evaluation order |
| Control region | branches, joins, loop successors | exceptional/suspend/cleanup paths; reachable-state analysis |
| Source map | byte/span identity + revalidation | token-preserving edits, version migration, cross-file transactions |
| Graph projection | layout positions, collapsed sets, LOD | user filters, viewport virtualization, scroll/camera persistence |
| Compiler/toolchain | native program remains owner | frontend adapter, toolchain config, diagnostics, compiler proof |

## Language adapter strategy

Frontend adapters should provide parse → symbol/scope index → typed operation and control descriptions → optional source transformers. They must explicitly advertise capabilities (inspect, type-check, edit, run, debug, compile). LSP/DAP integrations can supply intelligence and debugging but are **not** substitutes for a correct source-to-graph and graph-to-source contract. Reuse existing Python, C/C++, Rust and other runtimes rather than implementing ad-hoc interpreters in Qt.

No generic operator is automatically equivalent across languages: overflow, dynamic dispatch, purity, property effects, lazy evaluation, aliasing, concurrency, exceptions, macros, and storage semantics differ. The shared visual operator component can stay common while exact language adapter behavior differs.

## Roadmap; do not claim these are implemented

- P0 host qualification: launch Qt on Linux and Windows, inspect whole-file layout, connection pins, container geometry, deletion/lifecycle, and high-DPI/zoom behavior. Run the new `qt_smoke` and try the provided examples.
- P0 source correctness: syntax-version differences; definite assignment; relative import resolving; symbol ID stability through nonsemantic edits; richer literal/default binding semantics; proper top-level statement control flow.
- P1 operators/control: `for`, `while`, break/continue, exceptions and cleanup, `async/await`, dynamic calls, keyword and starred args, safe short-circuit lowering, overloaded operators and effects.
- P1 graph-to-source edits: literal/parameter editing, statements insertion/deletion, validated operator replacement, connected value rewiring with two-way source diff, undo, externally modified-file conflicts and tests comparing actual Python behavior.
- P1 viewport: automatic graph layout, semantic zoom and virtualized region expansion, per-scope cameras and persisted presentation-only positions.
- P2 IDE services: LSP diagnostics/rename/refs, DAP debugger/breakpoints/watches, terminal/build/test integration, native compilers, source editors, projects and Git integration.
- P2 extensibility: validated per-language adapters with conformance fixtures and true capability gates. Unknown source must always remain inspectable without being falsely compiled from invented graph semantics.

## Test outcomes at authorship

- Headless regression suite: 31 discovered; all passing in this environment.
- Python syntax/static source checks: passed.
- Native PyQt6: **not installed in this build environment**; Qt GUI not run here, host smoke pending.
- The package is an independent v0.4 prototype and must not overwrite an existing production Studio checkout.
