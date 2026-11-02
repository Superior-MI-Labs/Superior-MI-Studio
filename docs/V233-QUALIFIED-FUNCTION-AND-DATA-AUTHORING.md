# v2.33 | Source-backed data connections and function result creation

## Architectural rule

A creation capability is a language-adapter-qualified *source transform*. A rendered card, observed operation, or drafted edge never directly grants source-writing permission. The parsed text remains authoritative. We **do not** maintain a second graph compiler or an alternative mutable AST model.

The single catalog in `studio_native/python_authoring.py` now advertises three explicitly supported lowering contracts. The `operation_catalog.qualified_operations()` projection and the existing `Node Library → Source operations` use those definitions directly. The editable draft templates remain separate until their source lowering becomes qualified.

## New source-backed transformations

1. `python.local-literal-return.v1`: For a direct, standalone Return in a function, insert an immutable-primitive local binding before it and replace only the original Return token with `return <new identifier>`. The existing parser will reconstruct a real Assignment, a Return, a data edge from the Assignment's output to the Return's value input, and a control edge between the same two source operations. This is an explicit user-approved semantic change, not a speculative automatic rewiring. The original Return must have a simple `Name` or `Constant` value (or no value); an expression with side effects is refused. The new name must be a valid, previously unused identifier across the function (including nested references/imports/arguments). Parameterless functions are supported.
2. `python.return-from-pass.v1`: In a function consisting only of a standalone `pass` (optionally following a docstring), replace it with a primitive-literal Return. The function's interface and actual return-site descriptor are then reconstructed from ordinary Python AST data. It does not synthesize an internal compiler Entry or Result operation.
3. `python.branch-early-return.v1`: Previously qualified Branch/Return transaction remains present. Primitive-literal checking is now shared, and UTF-8 Python parameter identifiers are encoded correctly instead of assuming ASCII.

All transformations call the preexisting `_validated_proposal()` and `apply_proposal()` code paths, including parse, compile, size, original-file identity, backup, explicit review and atomic replacement. They do not execute user code. AST comparisons guard unchanged statements and validate the exact resulting nodes. Only explicitly supported syntax and anchors are accepted. Comments, semicolons and inline statements that would make the transform ambiguous are refused.

## Qt ownership

Three buttons in the existing Source Operations panel are generated from adapter definitions; a common UI dispatcher gathers only the parameters required by each builder. They share the same reviewed-diff transaction. Availability uses the *selected canvas session route* and corresponding `PythonDocument` identity, not a stale global document or the current hover target. The original Branch button identity remains supported for previously qualified host tests.

## Qualification

- Python headless doctor: **436/436 passed** (v2.32: 419), including exact AST reparse, canonical graph edges, function result boundaries, CRLF/UTF-8, no-param and nested functions, rejected side effects/expressions, stale anchors, external file changes and source-tab identity checks.
- Complete ZIP and isolated installer are separately checked before release.
- Native Qt is **not** available to the build environment, so the new panel behavior and routing must pass host `RUN-ALL.sh` before calling the release native-qualified.

## Not yet supported

The user cannot freely drag arbitrary Branch/Loop/Function/Return nodes and compile them. There is no general-purpose Python control-flow compiler, no general-effect analysis, no arbitrary expression or assignment insertion, and no guaranteed equivalence for dynamic Python semantics. Literal assignment and Return construction are only the first qualified parts of the adapter catalog. Next: a typed expression/operand builder and qualified flow wiring with a source span and local dominance proof, after the present native host gate.

## Quick manual exercise

Open `examples/python-v12-qualified-authoring.py` from the File graph or Python editor. In **Node Library → Source operations**, choose `Branch · early return on None` for `identity`, `Local value → Return` for `constant_result` (or `identity`), or `Return · replace pass` for `unfinished`. Review the proposed diff before approval. The example is a real Python source file, not a simulated graph or a fake catalog entry. If an operation is applied, the installed source example changes on disk and a guarded backup is created; use a copy if you want repeatable exercises.
