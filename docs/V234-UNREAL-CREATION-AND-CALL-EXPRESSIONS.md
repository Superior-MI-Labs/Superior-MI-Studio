# v2.34 · Blueprint-aligned creation and nested module-call visibility

## Baseline and objective

WolfCat-Studio qualified v2.33 with 436 headless tests and native Qt smoke. The previous Node Library contained three safe but button-only source transformations; right-click or drag-from-pin could not discover them. Module-level Python calls were identified as real AST call sites but their pins showed no call arguments; nested calls could be obscured by the `CALL print` card, all module calls initially used (0,0) positions, and the module guard was an opaque block with no bounded flow.

## Unreal comparisons

Epic's [Placing Nodes](https://dev.epicgames.com/documentation/unreal-engine/placing-nodes-in-unreal-engine), [Connecting Nodes](https://dev.epicgames.com/documentation/unreal-engine/connecting-nodes-in-unreal-engine), and [Graph Editor](https://dev.epicgames.com/documentation/unreal-engine/graph-editor-for-the-blueprints-visual-scripting-editor-in-unreal-engine) distinguish context-sensitive right-click creation, searchable palette discovery, and a filtered menu after dragging a pin to empty space. Compatible creations can connect automatically. In the new design, all three surfaces must share qualified adapter operations rather than infer editability from drawn port types.

**v2.34 implements:**

1. `authoring_actions.py` is a pure query/projection over `python_authoring.definitions()` and its actual eligible anchors. It is **not** another catalog or compiler. All searches and pin matches use the same IDs as the dock buttons and source-diff authoring pipeline.
2. `GraphCanvas` opens a searchable action chooser from right-click on empty Python graph space. Dragging a compatible parameter output to empty space opens the same chooser, filtered to a source-verified, pin-compatible `Return parameter` action. Other pins never imply unsupported conversions.
3. The new `python.return-parameter-from-pass.v1` lowering constructs a real `return parameter` from a function placeholder. It checks the exact parameter/port ID and `pass` AST anchor, produces a reviewed proposal, and validates the reparsed AST before any save. The original guarded atomic source editor remains the sole write path.
4. A persistent Source Operations dock now offers a compact live search and continues to enumerate the same qualified definitions; observed parsed operations remain read-only unless a lowering is explicitly qualified.

### Python module-call example

```python
if __name__ == '__main__':
    print(choose(3, 9))
    print(nested_expression(1, 2, 3, 4))
    print(early_exit(-1))
```

The module AST projection now gives each call argument an input pin with its exact source expression preview. A **direct nested call** supplies a source-backed data wire to the consuming argument of `print`. AST-qualified call evaluation produces a white execution wire from nested call to `print`, and ordered calls in the same simple suite connect in source order. The top-level `IF` for a simple call-only suite is a single Branch with a `True` execution output and an inline predicate preview, not a nested graph. The `False` exit remains unconnected rather than claiming an unproven target. Call cards now receive distinct source-line rows and nested-left-of-caller positions instead of stacking at (0,0).

This is **not** static proof of function dispatch or purity. Python names can be rebound, calls may raise exceptions, and even nominally simple calls may have effects. Execution wires here mean only the source AST's **possible completion order** for the bounded simple subset. Arbitrary attribute access, starred/unpacked arguments, generator/complex expressions, or unhandled control suites remain source-backed without inferred execution edges. Data references are similarly qualified as syntactic expression dependencies, not guaranteed runtime values.

## Preserved invariants

- Source text/AST is authoritative; opening the file never runs it.
- Function Entry and Return interfaces, and formal definition-versus-call roles, remain unchanged.
- Panning, minimap Qt ownership, graph routes, validated descriptors, node identity, backup and diff review remain on their established paths.
- Unsupported pin-based creation fails closed; there is no generic drag-a-pin Python compiler.
- The new UI is not qualified until native Mint tests pass. Headless checks do not prove modal/dialog layout, visual density, or mouse events.

## Qualification

Headless regressions (445 passing tests) cover source-catalog/menus, exact pin compatibility, stale anchors, approved node-to-source-to-node creation, nested `print`/`choose`/`nested_expression`/`early_exit` expressions, stable IDs, control edges, and opacity of unsupported forms. Native `qt_smoke.py` checks the searchable modal and pin filtering, plus exact module call cards and optional `module-nested-calls.png` evidence captured by `RUN-ALL.sh`.

## Next

Expand the same catalog and guarded lowering contracts to connected comparisons, general Branch inputs, and explicit function call construction. A node must never claim visual authoring support merely because its source representation can be parsed or displayed. Deeper universal graph tab-state migration remains separate and should not be confused with the source compiler contract.
