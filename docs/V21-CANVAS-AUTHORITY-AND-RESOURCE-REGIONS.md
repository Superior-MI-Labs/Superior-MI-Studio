# Superior MI Studio v2.1 — Canvas authorities, nested directories, and symbol evidence

## Startup crash diagnosis and correction

At v2.0 startup `NativeLab` creates four canvases before opening a `.py` file. In `GraphCanvas.rebuild`, `source_view=True` and `source_graph=None` fell through to `describe_graph(window.state, origin='draft')`, while node creation separately read `source_nodes()` (an empty list). The validated node IDs did not exist in the source node lookup, producing `KeyError: 'node-…'` before Qt smoke testing could proceed.

**Root-level fix:** `canvas_graph_source()` (Qt-free, `semantic_contract.py`) selects exactly one authoritative graph based on the canvas role, and returns `None` for an unloaded source/resource canvas. `GraphCanvas.rebuild()` now uses that selection and never substitutes draft data for missing source data. Any subsequent descriptor/view inconsistency raises a targeted `ContractError`, not an unexplained `KeyError`. The Qt-host smoke test now explicitly checks the unloaded Python canvas at launch.

## Read-only recursive filesystem

`directory_graph(..., expanded_paths=...)` projects explicitly expanded folders into child graph regions using the existing `GraphSurfaceItem`, `NodeItem`, and same validated descriptors. Double-click a directory to expand/collapse in the current workspace; Ctrl+double-click to navigate into it. Double-click a `.py` file to open its source graph. Non-Python resources remain read-only.

- No background crawling, file imports, file execution, or filesystem writes.
- Directory pages are bounded at 72 root entries and 18 entries per expanded folder. At most 180 graph nodes and three inline expansion levels are projected.
- Symlinks remain leaves. Invalid/inaccessible folders fail closed.
- Display identity derives from the resource path; expanding does not invent programming operations.
- Parent and child graph cameras remain presentation-only. Expansion does not forcibly recenter the root camera.

## Cross-file syntax evidence

When **Import links** is enabled, the resource adapter can additionally match an explicit `from helper import symbol` against direct top-level declarations in the sibling file **already present in the directory page**. The evidence tooltip includes the import statement and the target declaration's file and line. This is a *syntactic-name match*, not a claim about runtime import resolution or execution. Dynamic imports, packages outside the bounded snapshot, symlinks, and unavailable/unparseable files remain unresolved.

## Validation

- All original 183 v2.0 headless tests remain in the suite.
- Added tests: unloaded canvas authorities, nested resource ownership and clipping metadata, bounded traversal, symlink exclusion, symbol declaration evidence, and no-source-execution safeguards.
- Headless Python compilation, unit tests, shell syntax checks, package ZIP integrity, and launcher permissions are release gates.
- **Qt-host verification remains necessary.** `./test-qt-offscreen.sh` includes the new startup and inline-resource assertions; without PyQt6 in the build environment, they are not considered passed until run on the user's machine.

## Next architectural migrations

1. Move entire node/port presentation payloads to the validated contract instead of only membership/order; keep separate program and resource authorities.
2. Add region-aware association routing to avoid files' import/reference links obscuring their nested content.
3. Extend language adapters with qualified multi-file symbol indexes, retaining explicit uncertainty and provenance.
