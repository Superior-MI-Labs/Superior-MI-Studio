# v2.42 | Chained dataflow authoring and deferred IDE review

## Baseline and decision

v2.41 was qualified on WolfCat-Studio: 534 headless tests and
`NATIVE_QT_SMOKE_PASS`. This release extends the **existing** adapter-owned
source proposal system, not a second Python parser, source writer, or graph.

## Delivered

1. Language-neutral `OperandReference` and `BinaryComposition` are **requests**
   describing a chosen operation and input ports. They are not executable
   nodes, AST representations, or another semantic source of truth.
2. The Python adapter resolves those references against a straight-line
   function body with a final direct Return. It supports inputs from named
   parameters and previously assigned, once-bound local results. It refuses
   control regions, rebinding, unqualified local expressions, decorators,
   async functions, stale Return spans and unsupported source edits.
3. `+`, `-`, `*`, `==`, `!=`, `<`, `<=`, `>` and `>=` are the currently
   qualified syntactic operations. Python runtime types, overloaded
   operators and side effects remain dynamic and **not** statically proved.
4. Creating a local result does not re-evaluate its source producer. Users
   can choose whether to connect the new local to the final Return or keep
   that Return intact to wire further work. Replacing a Return expression
   that may contain effects is refused.
5. One adapter-backed capability appears in the existing Node Library,
   right-click search and eligible source-projected parameter/local pin-drop
   menus. All entry points use the same diff review and atomic save gate.
6. The Python-first test gate now composes two local operations from an
   originally empty file and checks parity with handwritten source graphs.

## Known limitations; do not call Python finished

A source-backed sequence of locals is not full SSA. No arbitrary drag to
reorder effects, no cross-branch local dominance analysis, no exception/
finally or async lowering, no arbitrary function signature refactors, no
full source undo transaction history. Source-view reparse validates syntax;
we do not execute user scripts as part of test qualification.

## Deferred full IDE review (before any second language adapter)

Study the extensibility/tooling model of mature IDEs such as VS Code:
separation of extension host from UI, LSP and diagnostics, debug adapter,
tasks and test runners, project/workspace indexing, commands/keybindings,
terminal and build tools, safe extension packaging and permission models.
Study the *contracts and security boundaries*, not a clone of VS Code's
technology stack. Evaluate compatibility with Superior MI Studio's
universal graph + document authority. Require a real user-driven Python
program built entirely through visual nodes, the same program written in
text, graph equivalence, round-trip source diffs, and full host GUI evidence.
This review is deliberately **pending**.

## Qualification

`./doctor.sh` runs the headless tests and Python-first gate. The real
Qt smoke test exercises the catalog and local-producer pin on a Linux host.
Safe installation keeps prior versions and logs when Qt fails.
