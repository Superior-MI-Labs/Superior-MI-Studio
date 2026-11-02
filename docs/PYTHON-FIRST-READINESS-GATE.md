# Python-first readiness gate before additional languages

This is a deliberately strict **pending** release acceptance contract, not a claim of Python completeness. A passing v2.40 test suite qualifies only the bounded authoring capabilities that were actually tested.

## Must pass before a second language adapter is considered

1. **Authoring from scratch:** create an empty `.py` file in Qt, add several functions and a guarded entry point through graph menus, wire data and execution, save and reopen; no text scaffolding required. Compare the source graph against an equivalent handwritten program.
2. **Bidirectional scope:** text edits to definitions, calls, arguments, names, assignments, conditionals, loops, exceptions and returns reproject correctly, including nested scopes and module call order. Graph edits to qualified constructs lower back to source with an exact reviewed diff.
3. **Function interface propagation:** function Entry and Result control, parameter type/name/order/default changes, Return changes, call argument and keyword updates, multiple return sites; unqualified dynamic calls produce explicit refusal or review, never silent corruption.
4. **Flow semantics:** Python short-circuit, exception/finally, break/continue, yield/await, loops with else, multiple branches, rebinding, aliasing, closures and async need explicit supported/unsupported status. No invented execution wires, no second evaluation of effectful calls.
5. **Source preservation and safety:** UTF-8 source identity, encoding, CRLF/LF, comments, formatting, imports, decorators, source ranges, stale documents, concurrent tab sessions, unsaved changes, backups and atomic saves tested. Source viewing must never execute code.
6. **Native visual UX:** type/port identity, wire preview, searchable pin-drop creation, collapse/focus, selected-parent panning, minimap containment, independent tab/camera state, breadcrumbs, docking, undo/redo, keyboard shortcuts, large-file bounds and accessibility.
7. **Tests:** Python examples and real software files; code->graph->code semantic equivalence, graph->code->graph equivalence, rejected unsupported edits, native Qt screenshots, repeated host install preservation and explicit user-approved execution smoke tests.

## Current state after v2.41

- Implemented: bounded AST-backed graph projection, Branch/Loop identity, source-qualified node library, function/return/call authoring, safe edge rewrite subsets, multi-function Python program construction from blank source with qualified Branch/For/While bodies, local optional-parameter migration. The capability descriptor contract is language-neutral while Python owns all lowering and editing.
- Still pending: general visual programming of arbitrary programs, full graph-to-source compiler semantics, complete function interface editing, robust undo/redo for source edits, cross-file impact analysis, advanced Python constructs, exhaustive native UX qualification.
- Gate command: `python3 scripts/python-first-gate.py` (small deterministic source and visual parity audit; **not** a full language gate).

The final review should include examples the user develops both visually and with text, and should be documented as an explicit go/no-go decision. Do not count passing static tests as equivalent to native user-facing qualification.

## v2.42 additions to Python-first qualification

- A source-backed binary composition can reuse an existing parameter or
  qualified local value without duplicating the producer expression. It can
  insert an intermediate local or connect the result to a direct Return.
- Chained compositions from an empty file must reparse into graph-equivalent
  operations to handwritten Python. The gate covers this; nested/dynamic
  effects and general graph rearrangement still remain unsupported.
- Final Python review must include the user building and editing programs in
  the actual GUI, and VS Code-inspired IDE maturity: extension-host boundary,
  language server protocol tooling, debugger adapter protocol, task/test
  runners, diagnostics, terminal, settings, keybindings, workspace trust,
  extension permissions, and multi-file undo/recovery. None is implicitly
  qualified just because the prototype parses Python.
- Future language adapters must use the shared graph and capability contract;
  **do not** transplant Python AST syntax, lexical rules or source splices into
  the language-neutral contract.
