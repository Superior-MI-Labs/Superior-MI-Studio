# v2.119: bounded conditional expression proof and release-process supervision

## Accepted ownership and semantic constraints

SourceDocumentSession owns the original independent Python source; ProgramGraph owns the executable graph. The existing Python lowering/compiler owns all semantic proof. A copied candidate may replace an `ast.IfExp` with an `ast.Constant` only after its condition and *both* alternatives are themselves exact compile-time constant values of the same supported type, integer or Boolean. All integer values must satisfy the existing signed 63-bit magnitude bound. A short-circuit condition cannot justify discarding an effectful or unknown alternative; if either arm is not a fixed supported literal, reject the candidate. The function AST normalization is bounded at 4096 nodes. No Python code is executed, no graph nodes are invented, no source bytes are changed and the strict generated-source import remains unchanged. Every explicit import still recomputes revision/digest guards and full trial-graph lowering as one undoable transaction.

## Qualification authority

`RUN-ALL.sh` remains the sole doctor/Qt qualification runner and writes a `qualification-verdict.txt` with doctor and Qt exit statuses before archiving, so subprocess output-pipe problems are diagnosable. `install_linux.py` owns install, process isolation, old-version retention and promotion; it supervises the full runner and descendants in one private Linux process group with a bounded configurable deadline. Timeout returns failure (124), terminates the group and never prunes previous installations. The durable verdict is only evidence: the process exit code is the gate. These changes do not claim to solve every historical wrapper stall and native Qt on WolfCat-Studio must still pass.

## Regression contracts

`tests/test_v2119_source_constant_proof.py` exercises conditional integer and Boolean source spelling, nested fixed arithmetic/comparisons, no-op proof, atomic import/undo/source preservation, generated-source strictness and unsafe alternatives. `tests/test_v2119_release_supervision.py` exercises successful and failed runner exits, descendant timeout, invalid timeout settings and archived verdict. Existing v2.118 expression, v2.117 watchdog, installer, and Qt suites remain authoritative.
