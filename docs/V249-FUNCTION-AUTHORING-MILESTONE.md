# v2.49 | Source-backed function authoring milestone

## Baseline and evidence

- Baseline: v2.48 source ZIP. The uploaded WolfCat-Studio report `qualification-20261030-163441-31663.tar.gz` records **579/579 tests, Python-first gate PASS and native Qt smoke PASS without traceback**. This is host qualification of v2.48, **not v2.49**.
- v2.49: headless regression suite and expanded Python-first gate execute in this sandbox, without PyQt6. Native Qt interactions are **pending user host qualification**.
- One source authority: `PythonDocument` AST/symbol analysis; `python_authoring.py` validates and emits proposals; `python_edit.py` handles syntax/roundtrip and preimage save; `available_actions()` supplies qualified UI actions. `gui.py` only gathers input, displays a reviewable diff and requests the existing save path.

## Complete workflow

1. Create module-level functions and parameters through existing source-qualified builders; use existing Return builders to establish results.
2. Call a uniquely resolved, non-decorated module function with 1–4 declared required positional inputs from stored prior locals, parameters or parsed primitive literals. A single Qt form specifies the function, every argument, a fresh result local and whether to feed final Return. The stored source call may have side effects, and is never treated as pure.
3. Use the once-evaluated Call result in later arithmetic or further Calls. The existing ` _qualified_composition_scope` gate now permits only exact, direct, unambiguous stored calls whose arguments are proven single-path input values; arbitrary calls and control-flow effects still fail closed.
4. Rename qualified module functions and update their direct local calls. Rename qualified function inputs and update exact body references and direct keyword call sites. Expressions and positional call arguments remain unchanged. The renamed source reparses and the graph is rebuilt from the file.
5. Discover the same actions from the Operations catalog, context search and, when qualified, from My Python selected symbols. Stored call also supports a source-exact output pin route.

## Design alternatives

- **Independent Blueprint compiler or GUI-owned mutable call graph:** REJECT. This would create a second source authority and inconsistent Python behavior.
- **Text replacement using source labels or global regular expressions:** REJECT. Rebinding, Unicode byte offsets and keyword call references would be unsafe.
- **Adapter-scoped AST proof + exact byte-span proposals + existing transaction, with thin Qt forms:** IMPLEMENT. The existing project remains the source of truth and both visual and text views are regenerated from the same source.

## Refusal boundaries and honest limitations

- Stored Calls require an eligible synchronous direct module function with 1–4 required positional inputs. Existing complex decorators, kwargs, variadic signatures, ambiguous callee bindings, crossing scopes, multiline unsafe anchors, rebinding, branches, loops, and effectful values that cannot be proven stable do not qualify.
- A stored Call is a real effectful invocation, not an arithmetic expression or a guarantee of purity. Users choose its location. The adapter does not execute user Python to validate a proposal.
- Rename is **single-file**, not a project-wide LSP refactoring. Function aliases, dynamic rebinding, imports, external consumers, decorators, reflection and `__all__` require manual review or are refused. Parameter rename refuses starred/double-starred direct calls, nested closures/comprehensions, rebinding, unsupported signature structure and name collisions. Unknown external callers cannot be modified.
- Existing text editing remains strict about syntactic validity; unrestricted visual dataflow, general Python control-flow editing, cross-file renaming, and inferred runtime types are not claimed.

## Qualification requirements

- Headless tests check creation, call chains, exact pins, call effects, Unicode/CRLF, direct and keyword argument updates, recursive renaming, rejection of ambiguous bindings, graph identity, stale files and no unintended source writes.
- The Python-first gate constructs multi-function code from empty source through adapter proposals, binds a real function call, consumes its stored result, renames a parameter and the callee, then compares AST and source graph against handwritten code.
- Native Qt smoke checks all new catalog buttons, direct-call modal fields, source-proposal preview without writing to disk, and My Python parameter selection enabling Call/Rename. A real Linux Mint report is required before accepting Qt behavior as qualified.

## Next architecture milestone

Finish intuitive direct graph editing gestures and function-node interfaces: visually connect source-proven data/exec wires, predictable deletion and reconnection, undo/redo of source proposals, Python text edits that can retain invalid intermediate states, and explicit visual control-flow authoring. No second scene, parser, symbol registry, or save mechanism.
