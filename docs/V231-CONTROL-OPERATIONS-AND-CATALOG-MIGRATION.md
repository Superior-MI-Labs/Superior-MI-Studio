# v2.31 — Canonical Control Operations / One Source-Backed Catalog

## Baseline and qualification

- Source: v2.30, qualified on WolfCat-Studio (401 headless regressions and `NATIVE_QT_SMOKE_PASS` in `qualification-20261029-071309-230760.tar.gz`).
- Current v2.31 package: 409 headless tests passed, including eight migration tests and updates to older test expectations. Native Qt remains **unqualified** until the user runs `RUN-ALL.sh` on Linux Mint.
- No source parser replacement, new execution engine, file mutation path, or arbitrary node-to-code generation was added.

## Architecture decision

Before v2.31, `composite_file_graph` turned an `IF`/loop into an implicitly nested graph viewport and reassigned its body nodes to that viewport. That presentation fused source operations with navigational/organizational regions. It also made focusing and collapsing the same operation appear semantically different and made future visual editing ambiguous.

**Now:** Python IF/ELIF and FOR/WHILE remain compact standalone source-backed control operations in their enclosing lexical function graph. The adapter's existing white execution ports and edges are preserved. Body statement nodes share the function graph and use their exact source IDs. `NodeDescriptor` forbids a control operation from owning an implicit child graph. Legacy `collapsed_regions` saved keys are accepted but cannot hide executable statements. Function definitions continue to own child implementation graphs and their source-backed function boundary interfaces. File resources continue to own their resource content graphs.

The module-level Python `if __name__ == '__main__'` guard remains conservatively projected as an opaque source-backed statement plus actual calls, not a fictional fully qualified branch. This is a remaining Python-adapter limitation, and unsupported semantics are not promoted to executable visual authoring.

## Implementation alternatives compared

**A. Keep implicit nested IF/loop viewports and rename the nodes.** Minimal short-term UI disruption, but preserves two competing roles (operation and container) and duplicates inside/outside pins. Rejected.

**B. Flatten the presentation by reparenting Qt widgets only.** Preserves the parser projection but makes Qt responsible for semantic containment and layout correction, creating a second view authority. Rejected.

**C. Make the source adapter project control operations directly into the owning lexical graph; keep reusable Qt renderer unchanged.** One source of truth, straightforward round-trip identity, smallest long-term maintenance surface. Implemented.

## Library model

The **existing Node Library dock** now includes two modes:

- Draft templates: current editable prototype nodes, with the existing draft-state mutation authority.
- Source operations: read-only observations from `observed_operations(GraphDescriptor)`. Double-click locates a visible source occurrence and highlights source. No menu item advertises source-node creation yet.

Do not merge draft templates with source operator definitions until a language adapter provides a versioned definition plus validated source creation/rewiring transforms. The catalog is a projection from the canonical validated graph, not a manually maintained second parser or node registry.

## Unreal compatibility principles

- Branch is one operation with a boolean condition and True/False execution outputs, not a graph container.
- Loops are operations with language-appropriate execution paths; an internal body is not an implicit graph tunnel.
- Functions have distinct definition, body entry, return/result and external call-site semantics. A function definition does not itself emit a runtime result.
- Collapsed graphs and macros are explicit organizational/executable constructs with declared interfaces. Do not invent them while parsing every source `if` or `for`.

This aligns the semantics with the proven Blueprint mental model without assuming Python/C++/Rust have identical purity, exception, evaluation-order, or ownership rules.

## Tests and native host requirements

1. Run `bash ./RUN-ALL.sh --launch` on WolfCat-Studio after installation; upload the generated report even on failure.
2. Inspect `operation-catalog.png`, `focused-region.png`, `nested-boundary.png`, `early-exit.png`, and `return-boundary.png`: branch and loop cards should be compact, not giant graph frames; functions remain inspectable graph containers.
3. Check Branch True/False, loop Body/Completed, folded and early returns remain visible, connect to the correct source-backed pins, and changing focus/expansion doesn't change source text.
4. Verify the **Node Library → Source operations** tab shows observed Branch/Loop/definition without providing an unqualified create action. Double-click a visible occurrence to locate its node/source selection.
5. Verify file resource, multi-tab navigation, dock controls and minimap remain functional. These systems were not otherwise modified.
6. A release cannot be declared native-qualified from headless tests or static inspection alone.

## Next architecture work

1. Standardize the *function implementation* interface around adapter-derived entry/result records and actual call-site contracts. Do not fabricate execution edges when source semantics are unknown.
2. Design a small versioned source-operation definition contract for a first limited Python visual authoring action, separate from observed occurrence census. Use existing proposal/diff/reparse/atomic-save pipeline, never direct graph mutation of source semantics.
3. Prove one round trip: build a conditional expression from qualified catalog definitions → propose Python source → review/syntax validate → parse again → compare canonical graph ports and execution paths.
4. Consolidate the remaining global Qt view-context aliases and remove compatibility-only root views once mixed resource/source tabs have been host-qualified.
5. Start the second language adapter only when the semantic and source-edit contracts are stable. Do not add a language-specific Qt renderer.
