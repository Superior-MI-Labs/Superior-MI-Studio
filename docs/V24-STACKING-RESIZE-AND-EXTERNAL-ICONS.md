# v2.4 — Unified stacking, resize handles, compact resources, optional atlas

This change retains the one Qt scene, recursive `GraphSurfaceItem`, the single validated graph contract, and all source/runtime boundaries from v2.3. No alternative rendering engine was introduced.

## Behavior

- Selecting/clicking a node lifts it above sibling nodes **in that same surface**. Its owning composite ancestors are raised in their parent surfaces. Node coordinates remain unchanged; source does not mutate. No push/reflow algorithm runs on expansion.
- A small `−` / `+` button in the right of an expandable source or folder header collapses/expands that **same** region. Double-click remains available. Regular atomic nodes do not receive a fake expand button.
- Eight resize zones (N, S, E, W, NE, NW, SE, SW) use one Qt-free geometry contract in `graph_surface.py`, shared by the canvas controller and source node. Ports are hit-tested first so border resizing cannot steal port drags. Parent-local opposite edges remain stationary on top/left resizing.
- Directory expansion retains stable file/folder positions rather than automatically shuffling siblings; user-moved positions are retained in a view-only session dictionary keyed by resource ID. Expanded nodes may overlap neighbors; the active composite is raised. Nodes are never reparented by movement.
- File/folder resource cards default to a compact ~186×36 presentation (before scaling), with true full names retained in the graph data and tooltip; header labels are elided for available width. Directory expansion remains bounded. Resource names do not contain duplicate emoji before the file icon.
- Resource header icons prioritize an OS-provided file icon; the optional Universal Icon Vocabulary v4 is available for semantic programming icons and as a fallback. Without the external pack, built-in placeholders and OS icons work normally.

## Optional Universal Icon Vocabulary installation

The **icon pack is NOT a required dependency**, and is not bundled with this ZIP. The code reads the authoritative v4 `manifest.json` from a path such as:

- Linux per-user: `~/.local/share/superior-mi/icon-atlas/`
- Windows per-user: `%LOCALAPPDATA%\\SuperiorMILabs\\IconAtlas\\`

Either put `manifest.json` and the `sheets/` directory in the given directory or put a single named atlas subdirectory inside it. Use your GitHub-supplied installer or copy the **extracted contents** to that path. The `SMI_ICON_ATLAS_DIR` environment variable can override the lookup root. Studio does **not** download unknown GitHub content, silently update icons, or require network access. The pack is indexed from the authoritative manifest and sprite images are cropped on demand. This patch consumes RGBA sprite art; recoloring masks and user-selectable per-icon tint are a future renderer capability. Newer incompatible manifest versions must be explicitly qualified first.

Run `./doctor.sh` to see optional icon discovery status. The supplied v4 archive was independently checked to contain **2,192 indexed icons on 15 sheets**. The larger future package may have different content/schema, so it cannot be claimed compatible sight unseen.

## Native GUI qualification

Run `./test-qt-offscreen.sh` on Linux Mint. Offscreen warnings about `propagateSizeHints` are informational unless accompanied by a traceback or failed assertion. Host-only checks now exercise compact file geometry, all four edge handles, front-layer activation, and stability of manually moved folder positions across expansion/collapse. Actual painted output and interaction must be visually confirmed on the target machine; headless tests are not proof of Qt gestures.

## Verification boundaries

The default node builder's manually authored programming nodes and the Python AST-derived graph remain separately authoritative for their respective content. The normalized descriptor controls identity and presentation metadata, but the renderer still retains legacy per-node dictionaries. No visual-source runtime editing scope has been expanded in this patch.
