# v2.46 — Python symbol navigation in the existing Node Library

## Baseline and scope

- Source baseline: supplied v2.45 ZIP. Last native host evidence is **v2.44** (`qualification-20261030-154601-28477.tar.gz`), 551 tests and a clean Qt smoke. v2.45 right-drag/selection controls have **not** been host-qualified in this handoff.
- v2.46 adds a **read-only** My Python browser, searchable by function, variable, parameter, class, lexical scope and source line. Double-click navigates to the real saved source scope/line and, where the adapter has an exact stable parameter ID, the parameter graph node.
- The same Node Library remains the owner of all UI tools. `PythonDocument.scopes`, `symtable` and parsed AST remain the only symbol authority. No independent model, source generator, drag/drop API, or compiler was introduced.
- The existing qualified builders remain in the **Operations** page with their unchanged source-diff review. A scrolling area now prevents the 15 builders from obscuring the observed operations inventory in short docks.
- Opening Python source is read-only and never executes code. The browser is a **partial** lexical navigation projection, not a static type system, LSP, index of imports, or proof that a Python symbol is currently bound at a runtime location. Unsupported Python bindings are omitted rather than guessed. Nonlocal/global references and list-comprehension bindings are not mislabeled as newly owned locals.

## Alternatives

**A. A new Blueprint-like symbol registry with draggable variables and full graph nodes. Rejected.** It duplicates Python's AST/symtable ownership; a mere drag cannot safely establish Python write/read semantics or scope/dominance, and would bypass guarded source lowering.

**B. Extend the existing `PythonDocument` projection and Node Library for discoverable navigation, without authoring. Implemented.** The parser supplies immutable navigation targets, the existing graph route changes the focused view, and the same source editor shows the line. The operation builder remains adapter-qualified.

## Qualification

- 564 headless Python regressions pass, including 7 new symbol browser tests: nested scopes, classes, variables, parameter locations, imports/comprehensions excluded, reassignment/global/nonlocal ownership, UTF-8 names, result bounds and refresh from reparsed source.
- Python-first construction gate unchanged and passing.
- Native smoke includes My Python page, search/filter, focus and source cursor location, no-file-change assertion, and optional `python-symbol-browser.png` screenshot in host report.
- PyQt6 unavailable in authoring sandbox; **v2.46 native Qt is not qualified**. User should run `RUN-ALL.sh` on Linux Mint and upload `qualification-*.tar.gz`.

## Next gate

Do not make browser items draggable simply to mimic Unreal. First qualify a variable-reference creation request through the existing source adapter: scope-aware name lookup, definite assignment before use, nonlocal/global handling, evaluated effects, safe insertion, verified source diff, and identical round-trip projection. The first user-test should confirm users can discover functions, navigate, and create a compatible node via the Operations page without learning internal adapter IDs. Review native UI size, nesting and filters before expanding the grammar.
