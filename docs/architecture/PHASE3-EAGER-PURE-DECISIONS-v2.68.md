# v2.68: Typed Boolean decisions and eager data selection

## Reviewed baseline and alternatives

Implementation starts from v2.67, with only v2.66 native qualification presently recorded. v2.67 publication UI is not promoted to host-qualified without its Linux report.

- **Alternative A: implement a Blueprint Branch by treating a Boolean expression as an execution control pin. Rejected.** The current compiler has only pure data dependencies. It cannot establish ordered effects, statement dominance, conditional execution, or Return paths from this structure. A cosmetic Branch would lie about execution.
- **Alternative B: introduce a distinct graph runtime/interpreter and select values there. Rejected.** It would duplicate the existing AST lowerer and the document authority.
- **Alternative C: extend the existing pure AST lowering with explicitly eager, typed value selection. Implemented.** The generated `IfExp` receives *already-bound* producer values, so both producer subgraphs evaluate before selection. This is a value multiplexer, not an execution Branch, and should not be marketed as conditional execution.

## Qualified operation contracts

`python.equal_int` compares two integer inputs and yields Boolean. `python.not` negates a Boolean. `python.select_int` and `python.select_bool` each consume a Boolean condition and two same-type values; both producer arms are evaluated and the selected value is returned. All four are v1 operations with exact input names, types, required ports, and no accepted arbitrary properties. `py:unknown` is permitted as a draft placeholder, but the lowerer validates inferred Python types strictly. No implicit `bool`→`int` conversion.

The sole editable authority remains `ProgramGraph`; presentation uses its existing `NODE_TEMPLATES` through `ProgramWorkspace.choose_node()`. Compilation, source mapping, and publication remain owned by `python_lowering.py`. Incomplete or unknown operations remain persistable but fail closed when lowered. No second operation registry or source writer was added.

## Evidence and remaining gates

`tests/test_v268_boolean_selection.py` covers integer and Boolean behavior, signed values, eager AST bindings, port and operation versions, type errors, unknown properties/operations, incomplete graph preservation, deterministic source mapping, geometry independence, publication, save/reopen, and publication refusal. The native ProgramGraph stage places the four nodes and reopens a saved incomplete graph; Linux PyQt6 execution remains host-only.

**Not implemented:** execution Branch/Loop, lazy conditional producer evaluation, mutable local variables/effects, control dominance, source-to-graph reconciliation, debugger, or further language adapters. These need an explicit effect and control-flow design before implementation.
