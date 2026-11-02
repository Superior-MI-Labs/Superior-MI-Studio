# v2.47 | Integrated variables and expression editing

## Source and evidence

Baseline: the supplied v2.46 archive. The most recent submitted native Qt host evidence is v2.44 (`qualification-20261030-154601-28477.tar.gz`), not v2.46. The v2.45 selection gestures, v2.46 symbol browser, and this patch still need a fresh combined Linux Mint qualification. This authoring environment has no PyQt6. No runtime performance or native GUI success is claimed.

## Milestone completed

One end-to-end, **adapter-qualified variable authoring slice**, not an isolated widget:

- **Create a fresh local** from a primitive literal or a verified parameter/earlier single-assignment local in a straight-line function. Optionally feed that new local to the final direct Return. The variable can subsequently be read by composition as a source value and appears in My Python from the reparsed AST.
- **Discover the same creation** through Node Library, right-click/Tab qualified creation search, an exact source parameter/local value pin-drop, or *My Python → Store selected value as a new variable*. The browser never invents binding or type information. Unsupported symbols cannot enable the operation.
- **One complete dialog per source operation** for both fresh assignment and binary composition instead of a chain of unrelated prompts. Preselected pin/browser sources are fixed and revalidated. A single eligible target avoids an unnecessary function selector. Both operations still finish through the existing source diff review and guarded save.
- **One source insertion/round-trip owner** (`_insert_fresh_local`) under `python_authoring.py`, shared by existing binary composition and new value assignment. No second AST, source editor, graph model, symbol registry, or filesystem save path.

The text source is authoritative. A variable action produces a *source assignment*, not a mutable Blueprint-style cell at runtime. The native source graph is always reparsed after a reviewed commit. A displayed occurrence does not authorize arbitrary mutation.

## Architectural choices

A. Make draggable variable nodes with direct GUI-based source rewrites. **Rejected**: visual state would claim lexical binding/dominance, introduce an alternate editor authority and be unsound for branches, loops and effects.

B. Add only a menu shortcut to the existing composition builder. **Rejected**: would not permit standalone literal/local creation, preserving Return, or a source-backed new variable.

C. Extend existing adapter proposals and action routing, then project the capability through the existing browser, pin search, and unified forms. **Implemented**. No direct Qt-to-disk writer and no generalized Python SSA promise.

## Safety boundaries

Only synchronous, undecorated functions with a final standalone direct Return and a safely inspected straight-line body qualify. Existing local producers must be once-bound, effect-free simple expressions; candidate references must already be available and dominating in the same lexical scope. New variables cannot shadow an existing occurrence in the function. Control flow, loops, `try`, `with`, rebinding, calls in existing local producers, unsupported node shapes and ambiguous anchors fail closed. Return rewrite refuses compound or effectful expressions. Primitive literals are parsed, not evaluated or executed. UTF-8 source bytes, newline convention, docstrings, and unrelated statements are preserved. Exact preimage CAS-style save guards refuse stale writes.

## Qualification

- **577/577 headless regressions passed**, including 13 new tests for chaining, source preservation, UTF-8/CRLF, empty-parameter functions, invalid or duplicate names, cross-scope reads, control barriers, stale writes, exact pin IDs and catalog consistency.
- Python-first construction gate **PASS**, expanded to construct `seed = value`, `two = 2`, `step = seed + two`, `total = step * 3` from an empty file using only qualified operations and compare generated vs handwritten graph projections.
- Native Qt smoke now checks browser eligibility, exact pin-drop action, and both modal form proposals without modifying the test source. **Not executed here**; the submitted v2.47 report from WolfCat-Studio must be reviewed before claiming native qualification.

## Next large patch candidate, after host result

Blueprint-style function authoring as one vertical slice: source-backed parameter declaration, typed/unknown pin presentation that does not fabricate Python types, function Return/dataflow wiring, call-site propagation where statically qualified, source-text parity, exception/stale-source defenses, and native tab/camera/selection interaction tests. Avoid adding many individually advertised templates without a composable authoring contract. A genuinely editable function workflow should be the next milestone, not another single button.
