# v2.5 — Persistent graph presentation, shared icon tinting and wire layering

## Scope and ownership

This patch follows v2.4 without creating another graph engine, parser, runtime, source editor, or icon registry. The existing **Python file remains authoritative** for Python, and the existing JSON Node Workspace remains authoritative for manually authored graphs. The new file in the user's configuration directory records **view state only**.

### 1. Persistence

`studio_native/presentation_state.py` owns one versioned, atomically replaced JSON snapshot:

- Linux: `${XDG_CONFIG_HOME:-~/.config}/superior-mi/studio/view-state.json`
- Windows: `%LOCALAPPDATA%\SuperiorMILabs\Studio\view-state.json`
- Override: `SMI_PRESENTATION_STATE_FILE` (intended for testing or portable setups)

It stores per-file and per-graph manual node positions, embedded graph camera offsets/zoom, root scene camera, embedded graph sizes, source scope expansion/collapse, selected/front sibling identity, file/folder navigation state, and positions for settings and resources.  File paths are **identifiers**, not fetched, read, or executed by the persistence module. Data never includes source text, node values, or graph connection mutations.

Writes are debounced and happen again during normal close. The configuration file has a version and bounded list/size/coordinate validation; snapshots are written via temporary file + atomic replace, not by truncating the current file first. Missing or incompatible files fall back to empty presentation state without deleting the original. View state is not a substitute for saving a user's edited Python or authored graph.

**Important regression fix:** Qt scene rebuild and automatic initial positioning no longer count as user movement, so auto-arranged graph coordinates do not overwrite saved manual positions. Different Python file paths never share the same node-position namespace. The draft workspace and settings graph also have distinct camera keys.

To reset only layout preferences, exit Studio and rename the `view-state.json` file. The source files and graph documents are unaffected.

### 2. Icons

The optional external Universal Icon Vocabulary stays outside the packaged application. The existing manifest reader is the single owner of lookup and crop coordinates. `icon_styles.py` resolves stable semantic IDs and optional tint hints for functions, loops, conditions, variables, calls, assignments, resources, and return nodes. The Qt icon cache applies source-alpha-preserving tint via `CompositionMode_SourceIn` to **a copied pixmap**, never by modifying the atlas. OS icons remain preferred for actual files.

At most two decoded sheets are retained in memory and the per-icon pixmap cache is capped at 512 entries so a future large atlas does not force Studio to keep every sheet decoded. Missing or incompatible packs fall back to OS icons or built-in placeholders; no network or GitHub dependency is introduced.

### 3. Shared wire layering

`edge_presentation.py` owns line width, color, dash, draw priority and opacity. Cross-region wires are drawn **behind nodes**, at a quieter visual weight. Data, control, call, reference, import, and return-facet relationships retain their original semantic identities, source provenance and endpoints. No new execution edges are invented.

### 4. Verification

- All 228 existing tests retained, plus 18 new headless checks = **246 tests**.
- Tests cover atomic save/reload, cross-document identities, camera/size records, malformed and future-version data, absent icons, semantic icon roles, v4 atlas vocabulary, and cross-region wire style.
- `qt_smoke.py` now uses an isolated temporary preference location and adds host-only checks for persisted presentation, selected stacking across rebuilds, and return/graph behavior.
- Native Qt visual interaction **has not been verified in the packaging environment**. Run `./test-qt-offscreen.sh` on Linux Mint and inspect a real window.

## Known boundaries / next steps

- Persisted positions are keyed by stable source node IDs. Structural source changes that replace an identity can cause affected nodes to revert to automatic layout, as intended; we should later add semantic identity migration with conflict detection.
- This does not yet provide global keyboard shortcuts or source-level syntax highlighting for all supported languages.
- Cross-file association resolution and automatic layout optimization remain ongoing. Cross-boundary wire routing is visually quieter, not yet a sophisticated obstacle-avoiding router.
- Large v5+ icon manifests have not yet been qualified; current parser requires v4 schema.
