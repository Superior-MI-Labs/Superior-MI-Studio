# v1.1 — Source bindings, real returns, and implicit loop repetition

## Problem and correction

A programming graph should not turn a basic `a = "a"; b = "b"; c = a + b; return c` sequence into generic `SET` boxes with unclear identity, duplicate literal cards, and unrelated wiring. Likewise, a `for` body does not require the programmer to draw a repeat connection into the loop header. These are **projection** issues, not evidence that Python requires a new intermediate runtime or a second graph-authoring store.

The source file remains authoritative. The AST/symbol table and `PythonDocument.scope_graph()` continue to supply the same source identities, expression/value dependencies, control flow, and guarded source-edit targets. `python_presentation.readable_scope_graph()` produces a *disposable* readable graph. Only the existing shared `NodeItem`/`PortItem` renderer draws it. The Analysis toggle retains all literal nodes, execution backedges, and version-analysis helpers for diagnosis.

## Explicit binding contract

The parser attaches `binding_name`, `binding_ownership`, and `binding_statement_kind` to assignments. The readable view classifies **first direct named local assignment in lexical source order**, conservatively excluding parameter rebinding, `global`/`nonlocal`, prior writes through conditionals/loops/unpacking/imports, and assignments inside nested definitions. `x: int` alone is not a runtime binding. This is **not** a new Python declaration keyword or proof of runtime dominance on arbitrary dynamic execution paths. Unsupported cases stay as SET/write operations.

A qualified first binding is shown as a compact node titled with the real source name, e.g. `a` or `total`, with an actual input port (`value`) and output port named for the binding. Source literals use the input's exact authored token text (`"a"`, `'a'`, `0`), preserve its `source_literal_span`, and remain double-click editable with diff review. A computed initializer shows its real incoming edge (`+` -> `c`). A subsequent reassignment remains `SET c`; an augmented write remains `c +=` or `c -=` without a duplicate setter.

A `return c` has a real return node with a named `c` input and a genuine producer edge when the current value is proven. A value modified in a loop may remain a named **current binding** without a false frozen-value edge from the initial assignment. This distinction is essential.

## Loop control presentation

Supported `for` and `while` loops retain the original control-flow analysis, but their Readable projection suppresses the **implicit** body-completion backedge and `repeat` port. The loop operation itself carries repeat semantics: body output enters real statements, and normal completion proceeds to its successor. Explicit `continue` still creates a real control transfer to the loop's execution input; `break` retains its explicit loop exit. Python `loop ... else` semantics and qualified analysis edges remain unchanged. Neither a `WHILE BODY` wrapper nor an invented loop-variable runtime exists.

The `for item in items` graph uses the `FOR item` node's genuine `item` output, a typed iterable input, `body` and `completed` outputs, and a single normal execution input. The `total += item` statement receives `item` and shows the current `total` binding; the authored initial `total = 0` remains its own variable node.

## Visual acceptance cases

### Straight-line bindings

```python
def combine_strings():
    a = "a"
    b = "b"
    c = a + b
    return c
```

Readable **five nodes**: `a`, `b`, `+`, `c`, `RETURN`. Actual data edges: `a -> +`, `b -> +`, `+ -> c`, `c -> RETURN`. The `"a"` and `"b"` inputs are editable inline. Source execution order remains in the authoritative analysis graph; the Readable view currently also retains the explicit source-statement control edges.

### For loop

```python
def sum_items(items):
    total = 0
    for item in items:
        total += item
    return total
```

Readable **five nodes**: `PARAMETER items`, `total` initialized `0`, `FOR item`, `total +=`, `RETURN`. The body executes `total += item`; the loop's normal completed output reaches return. Normal repetition is implicit and has **no redundant visible backedge**. A dashed reference to `total` means **symbol identity**, never a claim that the original `0` is the value on every iteration. `return total` reads the current binding.

## Limits and next architectural step

The analyzer is still Python-specific and uses some renderer-shaped records, not a fully normalized language-neutral IR. Do **not** claim that all Python value versions, side effects, dynamic types, closure rebinding, or graph-to-source edits are covered. These bounded changes do not authorize general rewiring through loops.

The next architectural gate is a canonical semantic record set for `Symbol`, `Binding`, `Read`, `Write`, `Expression`, `ControlRegion`, `Effect`, and `SourceSpan`, independent of Qt. Language adapters populate these contracts; the same view projection and node presentation components render them. Keep source-diff review and qualified transformations separate from presentation-only edits. No extra graph owners, variable stores, or hidden execution nodes.

## Qualification

Run `./doctor.sh` for Python parsing/tests, source identity, loops, editing safeguards and graph-port integrity. Run `./test-qt-offscreen.sh` on Linux Mint with PyQt6, then inspect the `combine_strings` and `sum_items` views with normal graphics and interaction. The Qt host check is **not** considered passed solely because headless tests pass.
