# v2.35 · Unified qualified expression creation

## Qualified baseline

WolfCat-Studio passed v2.34 (445 headless tests, native Qt smoke PASS). v2.35's GUI changes remain unverified until the new native Qt smoke runs on the host.

## Objective

Grow the same parser-backed Node Library and Blueprint-style graph/context-pin creation flows without a second compiler or misleading generic edge compatibility. A visually authored `BinOp`, `Compare`, `Branch`, or `Return` must reparse into the same Python adapter representation as typed source code.

## Design

1. **Six adapter-qualified capabilities** in `python_authoring.definitions()`. The new `python.arithmetic-return-from-pass.v1` creates a real parameter + numeric literal arithmetic expression wired to Return from a standalone `pass`. Qualified operations: +, -, *. Existing unrelated statements and bytes are preserved.
2. **Comparison to Branch** (`python.comparison-branch-return.v1`) creates an exact parameter comparison with one primitive on its right side, a true-path literal Return, and fallthrough into the original direct Return. Qualified comparisons are ==, !=, <, <=, >, >=. Dynamic operator semantics are not assumed pure or type-safe.
3. **One Branch insertion validator** now serves both the previous `is None` Branch builder and the new comparison builder; AST identity, return placement, unchanged statements and source syntax have one authoritative verification path. The adapter now refuses commented/inline Return locations at the *eligibility* boundary, instead of offering a creator that would later fail.
4. **One catalog, three entry points:** Node Library, empty-canvas searchable right-click, and exact parameter-pin drag. A pin/drop is qualified by real Python parameter node + port IDs and validated AST anchors; it never implies generic color-based compatibility. A parameter in a pass-only function offers Return and arithmetic creation. A parameter in a direct-return function offers comparison Branch creation. Other pins remain unsupported.
5. **One writer:** Every creation returns an `EditProposal`, invokes the same diff review, then goes through the existing guarded atomic apply / backup / reparse. No source file is changed before approval. Source remains the authority.

## Semantic round trips

**Arithmetic:** `def f(value): pass` => approved `return value + 2` => `PARAMETER`, `LITERAL`, `ADD`, `RETURN`. Data edges param→ADD, literal→ADD, ADD→RETURN; execution ENTRY→RETURN.

**Comparison:** `return value` => approved `if value < 0: return None; return value` (on separate Python lines) => `PARAMETER`, `LITERAL`, `LT`, `BRANCH`, two `RETURN` sites. Data edge LT→Branch condition, true exec to new Return and false exec to original Return.

Neither AST inspection nor graph projection executes source code. Python annotations are not enforced runtime types, and special methods may have side effects. These operators express the syntax the user chose, not certified purity or successful runtime execution.

## Validation and limits

456/456 headless tests pass including 11 v2.35 regressions. No PyQt6 is available in the package-build environment; native Mint qualification remains pending. Tests cover source-byte preservation prior to approval, true/false control paths, data edges, operator matrices, invalid operators, unsafe expressions, stale anchors, exact pin IDs, nested scopes, CRLF, Unicode, and refusal to overwrite externally changed files.

The builder remains intentionally scoped: it does not implement arbitrary graph wiring, operator inference, free-form expression compilation, call synthesis, control-flow dominance analysis, or reordering effectful source statements. Further language adapters must advertise their own qualified lowerings through the same contract.

## Next

Extend the canonical expression creator to typed function-call argument connections and value-producing assignments, then improve direct graph-edge editing. Do not infer arbitrary Python source semantics from rendered connector colors, nor instantiate operations merely because they appear in the observed catalog.
