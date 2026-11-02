# v1.0 architectural correction: source semantics vs internal analysis vs visible graph

## Why v0.9 became more complex than Python

For the actual source:

```python
def reduce_until_small(value):
    while value > 10:
        value -= 2
    return value
```

v0.9 drew **eight graph nodes** including compiler-analysis helpers `ENTRY`, `TEST`, `LOOP VALUE`, and separate literal `2`. These helpers are not authored operations; showing them as equal peers of `while` and `-=` made a two-statement loop harder to read than its source. The problem was **which semantic layer reached the UI**, not insufficient gradients or node-size tuning. The v0.9 analysis is retained for correctness and diagnostics; its output is *not* suitable as a default programming view.

## Root contract

```
real Python source  ->  ast/symtable analysis  ->  analysis graph
                                      |
                                      v
                       pure readable projection  ->  same Qt renderer
                                      |
                                      v
                     exact source identities + guarded edit proposals
```

`PythonDocument.scope_graph()` remains the full internal analysis graph. `PythonDocument.presentation_graph(detail='readable')` calls the *same* analysis and projects it through `python_presentation.py`. `whole_file_graph(...,detail='readable')` uses that projection for each expanded scope. `detail='analysis'` exposes the original diagnostic data. All nodes that survive use their **original stable source IDs**; no second authoring store, parser, runtime, or separate node renderer is introduced.

### Visible rules

1. `while` is a **single control operation**. It displays its exact condition, checks on every iteration, has body/completed flow, and receives its actual backedge. It does not require an artificial `TEST` statement node.
2. `value -= 2` is **one real augmented assignment**. The numeric operand is inline (`2`) and backed by the exact source span. Double-click proposes a literal replacement with the existing diff review. The input pin retains the same identity for compatible rewiring; unsafe loop rewiring is still refused by the original source-edit verifier.
3. `PARAMETER value` is a **real function interface binding**. A dashed reference means "same mutable binding," not "the initial value is carried unchanged." The `return value` pin can show its authored name without a misleading data wire from the parameter's initial value.
4. `ENTRY`, `EXIT`, `LOOP VALUE`, `VALUE MERGE`, and `CONTROL JOIN` are **analysis-only bookkeeping** in the readable view. Any nontrivial path dependence stays in analysis metadata / named input semantics; not an invented executable statement.
5. Literal nodes feeding ordinary inputs can be represented as an **inline default on the real target port**; their exact source location is retained. Connected inputs must override the display fallback, not silently create a second source of truth.
6. The full source graph remains accessible through **Readable / Analysis**. Switching changes only presentation. A view change never rewrites `.py`.
7. A binding that cannot be proven receives an **unresolved marker**, rather than a fabricated producer edge. Analysis stays conservative about unbound reads and loop effects.
8. Existing source edits remain **explicit**: validated proposed source diff → user approval → backup → write; source remains authoritative.

### Example v1.0 contract

Visible graph has four nodes:

- `PARAMETER value` (the real function argument)
- `WHILE value > 10` (the real loop condition and two flow exits)
- `value -=` with inline input `2` (the real assignment)
- `RETURN` with named `value` input (the real return)

Five visible relationships: `value` binding → while, `value` binding → update, while body → update, update next → while, while complete → return. No analysis-value or literal-card overhead.

### Known limits — do not overclaim

- This is a **first semantic/presentation split**, not yet a complete language-neutral IR. `scope_graph` still uses the legacy renderer-shaped analysis records. The next architectural cleanup should normalize definitions, bindings, control regions, and value/effect dependencies into typed semantic records, then project them through the same API.
- The compact projection keeps honest source text, but does **not** make ambiguous loops or Python side effects executable through graph rewiring. Their controls remain read-only until verified transformations exist.
- `for` loop item ports use the actual iteration binding; dashed binding references must not be treated as value snapshots. Complex indexing/destructuring/async syntax still needs its own language-specific lowering.
- Module-level executable statements and cross-file symbols are not fully decomposed. They remain source-backed and available for inspection.
- Native Qt appearance and interaction **must be qualified on a Linux host**; headless parser tests do not replace this.
- Some source graphs outside the simple loop still include compact expression/call nodes. Continue removing *unnecessary* complexity by rule, not by one-off cosmetic patches.

## Tests and acceptance gates

The 11 new v1.0 headless tests include: 8→4 node regression; control flow and repeat semantics; binding-reference versus frozen-value semantics; exact editable literal span; safeguarded rejection of loop-carried rewiring; contraction of branch joins while preserving both paths; ambiguous loop-value handling; real `for` iteration output; unresolved future local reads; whole-file/focus consistency; and deterministic source IDs without source mutation. The existing 83 tests remain intact. Run `./doctor.sh`; on the target machine run `./test-qt-offscreen.sh` and inspect the GUI.

**Decision rule for future work:** new technical analysis artifacts do not automatically become new author-facing node types. An apparent node must represent a source-level operation, a real binding/interface, or a user-explicit visualization of diagnostics. If it is compiler bookkeeping, it stays below the presentation boundary.
