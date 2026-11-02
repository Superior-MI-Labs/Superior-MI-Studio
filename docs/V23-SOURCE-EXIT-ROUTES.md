# v2.3: Source-Owned Exit Routes / Unified Appearance Contract

## Root-cause correction

The v2.2 UI connected early RETURN to the function boundary using a line beginning at `QPointF(site.width, site.height/2)` and a separately offset value line beginning at `site.height/2+12`. Those starts were not ports or stable terminal anchors, so wires visually missed the RETURN node and could differ from the actual binding location when card geometry changed. This is a presentation defect, not a missing language construct.

In v2.3, `ReturnFacetItem` is a child graphic of the RETURN card. Its positions are derived from the existing corresponding RETURN inputs (typed value and execution flow), while their output-facing facets lie on the right edge. There are **no new source-owned output ports** or source edges, and the nonlocal return is still an ordinary Python `ast.Return`.

The pure `project_exit_routes(GraphDescriptor)` produces `(site, owner, exit identity, control anchor, value input and value port, folded)` records from *one already validated semantic contract*. The GUI owns only painting and camera-space routing. It does not reconstruct source-level return ownership. Both value and control facets share a semantic exit while remaining visually distinct.

## Functional fixes included

- Standalone and nested function definitions have a proper return interface. A nested Python `def` remains a name-binding statement producing a callable; its child definition graph separately exposes an output contract so the implementation can be inspected and rewired. Its return port **does not** mean declaring the function executes its body.
- The boundary edit resolver uses the explicit interface category rather than assuming `source_kind=='function'`, so nested functions are eligible for the same guarded single-terminal transformation, without weakening multiple/early-return refusal.
- IF and loop regions do not acquire fabricated function return ports. Their body/true/false/completed interfaces retain their own semantics and nonlocal exits target the enclosing function.
- `AppearanceDescriptor` adds common presentational metadata to NodeDescriptor for each graph producer; the same Qt compact title reads this descriptor. The full modern renderer is *not yet* 100% descriptor-driven: geometry, containers and native controls still read the established view dictionaries. This is incremental migration, not competing authority.

## Regression gates

1. No synthetic source nodes, ports or edges introduced by the exit router.
2. A single terminal return is folded; multiple/early returns remain distinct.
3. A bare return has a control facet but no required value transfer.
4. RETURN inside loop / conditional routes to its enclosing FUNCTION.
5. Nested function return cannot target its enclosing different function.
6. Return sites must genuinely have source construct `return`.
7. Value output cannot use an execution port type.
8. Common appearance values are validated for source/draft/resource origins.
9. Live Qt smoke confirms physical path endpoints on return terminals.

The non-Qt suite has 220 passing tests; the Qt smoke is updated but **not run** in this container, where PyQt6 is unavailable. User host execution is required. More general execution-wire editing, yield/throw/cancellation routes, ownership-qualified cross-region value rewiring, and all-language adapters remain unfinished and must not be assumed functional.

## Next prioritized work

1. Move remaining geometry/control presentation off raw Python dictionaries onto the common GraphDescriptor, including validated type/interaction capabilities.
2. Establish a general route policy for nonlocal exceptions, yield, break and continue without treating them as normal return values. These require explicit source-adapter evidence and runtime correctness tests.
3. Improve automatic layout and edge visibility in expanded recursive graphs while retaining hand-placed positions and consistent camera/pan controls.
