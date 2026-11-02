# Python source graph v0.3 — authority, edges, and future extension

This is a separate native Qt development sandbox, not an update to the primary Studio codebase. It retains v0.2's `NodeItem`, `GraphCanvas`, `RowWidget`, `SectionWidget`, atlas loader, settings graph, and `smi.dynamic-node-lab` JSON authoring document. Parsed Python does **not** use that JSON format and is not saved as a replacement for Python source.

## Data owners

| Owner | Data | May mutate? |
| --- | --- | --- |
| `.py` file | Actual Python source and semantics | Only approved source transforms |
| `python_graph.PythonDocument` | In-memory AST, symbol tables, content digest and scope index | Recomputed from source |
| `scope_graph(key)` | Transient nodes, typed ports, edges, source spans, warnings | Recomputed per scope |
| Qt `GraphCanvas`/`NodeItem` | View layout/positions, collapse/filter/search | Presentation only |
| `python_edit` | Candidate bytes, syntax validation, unified diff, create-only backup | Commit only on approval |
| `model.py` browser-compatible prototype state | Manually authored node designs and settings | Remains separate from source graph |

## Graph topology

`module` has declarations, imports, simple module bindings and top-level opaque statements. Function/class declarations have `source_scope` keys for navigation. `Function` interfaces reflect positional/keyword args and return annotations; free/captured names are separate environment inputs. Module/global references are different from values passed as explicit arguments.

Inside a function, parameter/capture/global nodes supply source values, expression nodes derive operand input and result output ports, assignment nodes bind values, return nodes consume values. Nested function nodes reference deeper scopes rather than duplicating them. Explicit node IDs derive from scope/location/kind, edge IDs from endpoints and relation. This first static projection does not resolve general dynamic dispatch, shadowing under all control flow, or whole-program effects.

Edge relations: `data` (value use), `control` (only demonstrably straight-line adjacent statements), `reference` (source dependency), `call` (reserved for future inter-procedural call links; call nodes exist today). For unknown `if`, `for`, `while`, `try`, async and exception paths, display an **opaque source-backed region** rather than inventing CFG edges. Pseudo Python types are display-only `py:int`, `py:str`, `py:unknown`, etc. Python's `int` is unbounded and not equivalent to Studio's `u32/i32`.

## Editable subset

- From a Literal node: replace exactly one Python Constant token using a parsed literal, showing a diff.
- From an assignment or return node: wrap its expression in `(old expression) + numeric_literal`, showing a diff.
- Parsing and `compile()` validate the new text without executing it. Edits use UTF-8 source only, exact AST byte spans, a read-back digest guard, a create-only `.smi-backup` file and a temp-file `os.replace`.
- There is no cross-process lock/CAS. An external process can still replace a file at the narrow final-write boundary; never advertise this as solved.
- Errors in unsupported refactorings must be visible; a user dragging a source-derived pin must not mutate the file unless there is a defined source transformation.

## Running and syntax checking

`compile()` only checks Python syntax and bytecode generation without running the program. Native run uses `QProcess` and `sys.executable`, an explicit consent dialog, 8-second watchdog and 64-KiB output cap. It **does execute code with the user's full OS permissions** and is not sandboxed. There is no attached debugger, package manager, compiler toolchain dispatch or arbitrary cross-language execution.

## Future language adapter contract

A language adapter must eventually supply these capabilities independently and without inventing authority:

1. `parse(file) -> SyntaxSnapshot` with diagnostic support and exact source ranges, without running source.
2. `index_scopes(snapshot) -> ScopeTree` with module, class, function and language-specific block binding rules.
3. `resolve_symbols(snapshot, scope) -> Bindings + Dependencies` including uncertain/dynamic cases.
4. `project(scope) -> SourceGraph` whose pins and relations are derived; unsupported semantics remain opaque.
5. `plan_edit(selection, command) -> SourcePatch + Preconditions + Diagnostics` with defined changes, diff, safe persistence and undo/redo semantics.
6. Separate, explicitly qualified capabilities for `run`, `debug`, `test`, `build`, `compile`, and `language_server`, typically delegating to external tools (LSP, DAP, Python, GCC/Clang, Cargo, etc.).

Do not embed Python AST assumptions in the renderer and do not require every language to use Python's lexical/variable model. Common typed graph semantics need declared effect/ownership/flow relations and a versioned interface before in-place integration with canonical Superior MI Studio semantics.

## Test gates

`python3 -m unittest discover -s tests -v` must pass; does not require PyQt6. `./test-qt-offscreen.sh` must be run on Linux with PyQt6; it tests real Qt card creation, shell resizing after adding a container, and Python nested-scope navigation. Windows must also have its own native Qt test before Windows usability claims. No headless test proves native Qt behavior.
