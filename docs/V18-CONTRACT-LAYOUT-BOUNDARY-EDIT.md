# v1.8 — A single validated graph boundary, bounded layout and source-backed interface edits

This remains a **standalone native Qt research lab**, not an in-place replacement of the Superior MI Studio production repository.

## Architecture priorities covered

### 1. Shared renderer-neutral descriptors

`studio_native.semantic_contract` adds immutable `GraphDescriptor`, `NodeDescriptor`, `PortDescriptor`, `EdgeDescriptor` and `SourceLocation` values. The common `describe_graph` function validates node/port/edge identity, direction and relation, and distinguishes `origin='source'` from `origin='draft'`. The Qt graph canvas checks this contract before reconstructing either the real-source or authored workspace. It cannot infer that a prototype graph is executable, and it does not synthesize code, branches or casts.

**Source authority is unchanged:** `PythonDocument` plus the real `.py` file for Python; `model.py` for authored drafts. Descriptors are *snapshots* with immutable dataclass values, not another graph registry. The existing editor still displays the same node IDs, and source mutations still pass through the guarded `python_edit` proposal/backup workflow. The contract is versioned `1`. Semantic lowering, portable type checking and the future language-adapter interface are still unfinished. In particular, `type_id` is deliberately an opaque language-qualified string and no cross-language compatibility is inferred.

### 2. Layout does not control program meaning

`graph_layout.arrange` now computes a stable topological order for connected expressions on the same source line. This fixes a producer/consumer inversion caused by the old predecessor-count sort. Long same-line expression groups wrap to bounded rows without changing nodes or edges, and independent operations retain source order. All child regions use the same layout function. This is a first readability improvement; minimizing crossings of *all* cross-region or module-level wires is not yet solved. No unverified execution or dependency edge is added to reduce crossings.

### 3. Existing function ports are interactive *source* boundary aliases

For **one final, non-early `return` only**: drag an existing value-producing port to the inner `return` dot of an expanded function. Or start at the function's **inner parameter dot** and drop on a supported internal operand/return. The source and destination are resolved back to exact existing Python AST nodes and port IDs using `boundary_edit.py`. The original `python_edit.rewire_source_operand` validates the operation and opens a source diff requiring approval. Commit retains backups and stale-file/syntax checks. This does **not** turn arbitrary graph connections into runnable Python. `break`, `continue`, `yield`, multiple/early returns, uncertain cross-scope bindings, loop-carried variables and mutation through interface ports are not supported source edits and remain read-only.

The root/child graph surfaces, compact node families, Source Editor and Inspector defaults, and existing settings/UI remain unchanged.

## Qualification

- 163+ headless Python unit tests cover the existing prototype and the new descriptor, layout, and boundary edits.
- Headless tests open and normalize each bundled Python example, checking original `.py` bytes are unchanged.
- A real reviewed boundary-rewrite test replaces `return a` with `return b`, creates a backup and reparses Python. Early/multiple returns are rejected.
- Qt offscreen smoke script checks descriptor availability and inner-boundary hit testing, but this build container **does not have PyQt6**. It is **not host-verified** until run on the user's Linux Mint machine.

Run `./doctor.sh`, then `./test-qt-offscreen.sh` on Linux Mint. The graphical mouse gesture is not qualified by a headless analysis test alone.

## Next structural milestones

1. Validate the actual Qt dragging behavior and inspect a screenshot / smoke log, including selection and pan gestures after the new boundary feature.
2. Improve cross-composite edge routing through one common graph-surface boundary resolver, not per-Python-node special cases.
3. Define the next version of the language-neutral semantic contract: scopes, lexical binding, type constraints and effects, with a language-adapter conformance test suite. Do not migrate all languages or overwrite the existing lab until the contract has passing representative examples.
