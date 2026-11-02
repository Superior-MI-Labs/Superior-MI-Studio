# v1.7 semantic/presentation architecture audit

## Starting over: decisions I would change

**Keep** the native Qt scene, reusable node/port/edge graphics, recursive `GraphSurfaceItem`, one authoritative source file, static analysis, guarded source editing, and detail/Readable views. These foundations remain useful and are not being duplicated.

**Change** the order in which new language constructs become visual objects. The existing prototype often starts with a Python analysis node (e.g. `BRANCH`, `UPDATE total`) and then tries to simplify its title. That leaks compiler-analysis vocabulary into the editor. A new implementation should start from a language-independent **semantic construct** descriptor (conditional, loop, binding, read, augmented write, call, return, value expression, opaque source), then project it into an atomic node or composite graph region. This is not a new runtime or a new source authority.

**Change** the current `Node Workspace` authoring model versus parsed-source graph model. They already share the Qt renderer and near-identical `draft_ports` layouts, but have separate producers and different execution guarantees. In the next architectural migration they should satisfy a versioned, renderer-neutral descriptor with semantic IDs, port type/direction/role, optional source span, and optional child graph. Native authored nodes must not silently masquerade as parsed source operations. This is **not completed** in v1.7.

**Reject** a custom node class for every language syntax item, synthetic user-visible `BRANCH` nodes for an `if`, synthetic `LOOP VALUE`, `ENTRY`, `MERGE`, or `BODY` executable nodes, separate graphics scenes for every nested graph, source edits initiated by layout or camera changes, and a second authoritative programming graph alongside text files.

## v1.7 implemented corrections

1. An `ast.If` remains `source_kind='branch'` *internally* for backwards-compatible analysis and edit IDs, but its **Readable** presentation has `source_construct='conditional'` and a source-derived `IF`/`ELIF` title. It can own a recursive graph region through exactly the same `child_region_key` and Qt surface as `for` and `while`. The condition and true/false paths are real derived interfaces; there is no extra BRANCH operation visible by default.
2. An `ast.AugAssign` now has a compact `+=`, `-=`, etc. title/symbol and a separate, named `current_binding` input. The exact source target remains in `binding_name`, and its binding wire is a **reference**, not a frozen pre-loop data snapshot. Its right-hand operand keeps the same source-backed inline default and edit span, so `total -= 2` is still directly editable.
3. Child graph ownership is derived from nested source body ranges with the **innermost containing region winning**. This handles an `if` nested in a loop and a loop nested within another without adding independent special-purpose scene components. A conditional or loop body is **not** automatically a new lexical scope in Python.
4. Existing AST IDs, edge IDs, source file content, source editor and reviewed-save path remain unchanged by these presentation decisions. **Analysis** still retains detailed control/value-version helper nodes for safety verification.

## Remaining architectural gaps and priorities

1. **Formal normalized semantic schema and adapter contract.** The read-only `source_construct`/`semantic_role` metadata here is an incremental step, not the final multi-language IR. Design a frozen boundary between the parser and renderer, then migrate legacy producers one at a time with parity tests; do not write a competing semantic registry.
2. **Scope-aware and effect-aware source operations.** General visual rewiring through branches, loops and complex expressions remains unsupported until static analysis proves legality. Python `+=` may invoke in-place mutation; don't confuse it with a pure `+` function. No generic cross-language operator semantics are claimed.
3. **Further readable projection and layout.** Simple condition comparisons may be compacted into the IF header when provably safe; short-circuit and side-effecting expressions must retain ordered semantics. Cross-region edge routing and host Qt rendering need practical tests. Compound/early returns still need explicit exits; terminal returns may use function boundary dots.

## What counts as a passing qualification

- The `.py` source is unmodified by changing view, expanding/collapsing a region, or moving nodes.
- A source construct is not represented by duplicate executable nodes in Readable view.
- Graph node/port/edge IDs remain stable across Readable and Analysis, except for deliberately disposable analysis helpers.
- A nested IF inherits the same parent/child graph ownership rules as loops and definitions.
- All claimed source edits validate syntax, show a diff, refuse stale files, and retain an original backup.
- `doctor.sh` passes on the build host. Native Qt painting, scene event routing, resize, source highlight and drag-to-edit require the Linux/Windows host smoke test. This build environment lacks PyQt6.
