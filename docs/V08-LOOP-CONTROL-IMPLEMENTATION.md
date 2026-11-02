# v0.8 — Loop flow without a synthetic body node

## Decision and migration

v0.7 created an `opaque` node titled `WHILE BODY` / `FOR BODY`, containing source excerpts. That was a visualization placeholder, not a real Python operation, and it hid the actual statements inside the loop. It could not express body-to-test repeat edges, break/continue, or normal vs break completion.

v0.8 **removes both placeholder nodes**. A loop is one semantic control node with dynamic ports. Its `body` execution output reaches the *first supported real statement* in its Python `body`; the last normally completed body statement reaches `repeat`. `continue` routes to the nearest enclosing loop's `repeat` input, `break` routes to its `break` input. These are white Qt execution connectors; data values retain circular typed ports. Repeat connections detour around the top of the nodes for legibility.

For `for target in iterable`, the loop node also exposes an `item` data output when `target` is a simple name. For a `while`, the compact `TEST` value node describes the condition, evaluated on every entry/re-entry. The original Python expression remains authoritative; test operands that change during repetition are not incorrectly wired to pre-loop values.

### Loop interface (source graph only)

| Input | Meaning | When shown |
|---|---|---|
| `execute` (execution) | Enter loop | Always for supported loops |
| `condition` / `iterable` (data) | Test / iterable dependency | Always |
| `repeat` (execution) | Normal body completion or `continue` | When the loop can enter |
| `break` (execution) | Actual encountered `break` transfer | Only when there is a reachable `break` |
| `body` (execution) | Execute loop body statements | When the loop can enter |
| `completed` (execution) | Condition false / iterable exhausted | Absent for literal `while True` |
| `broken` (execution) | Break bypasses Python's `else` | Only with a reachable `break` |
| `item` (data) | Next for-loop item value | Supported simple-target `for` only |

An unconnected output is not executable. The visual CFG is a *static projection of real Python source*, not an alternative interpreter or compiler. The loop body's actual Python statements are still executed by Python if the user explicitly runs the script. The graph's control edges are currently inspection-only.

## Current lowering boundaries

Real statement nodes in supported loop bodies: simple `Assign`/`AnnAssign`, named `AugAssign` (now `UPDATE` with old-value/operand pins), `Return`, `If`/`elif`/`else`, nested `For`/`While`, nested function definitions, `Break`, `Continue`, `Pass`. Nested loops use their own nearest-loop control context. A loop `else` receives normal-completion flow only; a `break` bypasses `else`. Constant `while True` has no false-completion exit. Constant `while False` does not create a fake reachable body or mutate previous values.

Conservative/unsupported: arbitrary complex assignment targets and destructuring in `for`, `async for`, `try`/`except`/`finally`, `with`, `raise`, `yield`, `await`, ambiguous effects and other AST structures not yet lowered. Such constructs stay source-backed. The analyzer stops inferring a loop body backedge if it cannot prove the continuation. `for` iterable side effects and exception edges are not fully modeled. Not all Python scopes, call effects, loops, and complex analyses are complete.

Loop-carried data is not yet a full SSA/phi representation. `LOOP VALUE` and `UNCERTAIN` are *analysis bindings*, not executable code nodes, and represent values the static analyzer cannot establish as an invariant. Rewiring from these boundaries or loop `UPDATE` nodes is refused by the existing guarded source editor. We do not install new source-code operations or silently alter code from graph edges.

## Architecture safeguards

- One `LoopContext` analysis object holds nearest-loop repeat/break destinations and observed path counts. It is **not** persisted or displayed as a node.
- Loop nodes use the same `_node`, `draft_ports`, QGraphicsView, `PortItem`, and normal edges as all other Studio nodes. No separate loop renderer or `LoopBody` class exists.
- Full source spans are part of expression-node IDs. This corrects duplicate operator IDs when nested binary expressions share the same starting position.
- Node placement, backedge curve routing, and scope expansion are presentation only. Python source remains authoritative.
- The existing Qt picker, source-diff approval, backup, read-only unsupported edges, native node builder, and settings graph are preserved.

## Tests and qualification

Run `./doctor.sh` (headless) then `./test-qt-offscreen.sh` (needs PyQt6 on Linux). The v0.8 headless suite includes nearest-loop break and continue, for/while else, constant true/false while cases, nested loops, data uncertainties, source-edit rejection, stable source IDs, all shipped source graph port/edge validity, and previous functionality. The bundled `examples/python-v08-loop-control.py` produces known outputs when explicitly run by ordinary Python; the parser never runs it just to open it.

**Host GUI qualification remains pending.** In particular, validate that the compact `TEST`, `WHILE`, `FOR`, `UPDATE`, `BREAK`, and `CONTINUE` nodes fit their Qt shells and that the new repeat-edge route stays readable after manually dragging nodes. A passing headless suite alone does not establish Qt rendering, package installations on Linux, or Windows compatibility.
