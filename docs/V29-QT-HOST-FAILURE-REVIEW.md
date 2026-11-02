# v2.9 Native Qt host-failure recovery

## Evidence

User's v2.8 host report `qualification-20261028-234850-211536.tar.gz`: doctor passed (269 headless tests), Qt smoke failed at `qt_smoke.py:263` with `StopIteration`. The smoke invoked `set_all_scopes(True)` and then `navigate_source('module')` before asserting that the inner `INNER` definition exists in the current view. But module focus is not a recursive whole-file view. PythonDocument shows INNER in `module/function:outer:5:0`, and the expanded composite graph contains its embedded surface. The failure is a **test navigation/fixture mistake**, not proof of a product renderer defect.

## Scope and implementation choices

**Rejected:** push nested functions into the module scope merely to satisfy a smoke test. This would misrepresent Python lexical scope and damage adapter discipline. **Rejected:** swallow StopIteration or disable the native test. **Accepted:** interrogate INNER in the expanded composite before switching to Focus; independently verify MODULE and OUTER Focus semantics. Preserve assertion details and enable a screenshot of the nested boundary.

Updated only the existing Qt smoke test, RUN-ALL report environment, v2.8 shell-test screenshot assertions, version strings and docs; added one Qt-free suite for three scope/semantic invariants. Python graph analyzer, graph model, semantic descriptors, exit routing, runtime execution and source-edit pipeline remain unchanged.

## Test/qualification limitations

- Headless Python regressions and archive integrity are run in packaging environment; exact counts recorded in release response.
- Packaging environment has no PyQt6 and cannot download it; the native Qt smoke and its three screenshots **must** run on Linux Mint. A headless pass is not native GUI evidence.
- Full native test may uncover further GUI issues later in its 600+ line flow. Keep failing rather than marking green. Upload the report archive; subsequent patch follows actual traceback and images.

## Following patch priorities

1. Run full native Qt smoke and inspect images for clipped return wires, inner/outer execution facets, layer ordering and resizing. Fix host-proven issues.
2. Consolidate renderer input around normalized descriptors (one vertical slice, not a rewrite); make sure Python and resource providers share the same geometry and display contracts.
3. Improve source-backed execution/uncertainty visibility without inventing flow edges; qualify read-only second-language adapter only after normalized renderer usage and host tests are solid.
