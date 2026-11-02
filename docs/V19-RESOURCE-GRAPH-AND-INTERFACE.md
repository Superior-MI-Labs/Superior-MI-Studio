# v1.9 — Interface correctness + Files/System resource graph

Status: standalone Qt research prototype, **not** a merge into the production Superior MI Studio repository.

## Architecture work shipped

### 1. Function definition versus return value
- The `return` boundary remains one source-derived semantic port.
- On an **expanded** definition, the outer duplicate return graphic is suppressed and the inner boundary is the single visible return dot. A terminal source-backed return wire terminates at this same interface identity.
- `callable` retains its existing analysis metadata and stable ID, but is **not** shown as a second runtime-result dot on a function definition in readable view.
- Source `call` reference edges remain represented in analysis and validated descriptors. Their long definition-to-opaque-region wires are hidden in readable view rather than posing as execution or runtime data flow. This is a presentation change; it does not implement cross-file call resolution.
- The opaque top-level `IF` block now shows its actual `IF <condition>:` title; its synthesized analysis-only call-input ports are hidden in readable view. True editable call nodes within that region remain a future task.

### 2. Files / System browsing through the existing graph engine
- `resource_graph.py` is a deliberately small, independent **read-only** provider.
- One directory snapshot -> one ordinary graph of real child resources. Same `GraphCanvas`, `NodeItem`, ports and camera infrastructure as Python and authored graphs, **no extra Qt graph rendering stack**.
- New Files / System tab and contextual toolbar: Browse, Up, Refresh, Previous, Next.
- Directory double click navigates to its contents in the same graph tab; `.py` file double click opens the existing Python source graph+text editor. Unsupported file types remain read-only resource nodes.
- Symlinks are displayed, never followed by the filesystem provider; no implicit import/execution, no recursive scanning. File paths carry stable resource identifiers; resource snapshots are never a second copy of file contents.
- 72 items per page, page offset up to 720, enumeration capped at 50k entries (no unbounded eager recursion), stable case-insensitive ordering. Unreadable directories and unsafe symlink traversal fail with a visible status message.
- System root can be selected using Browse. Initial directory is `~/Projects` if present, otherwise home. No background scanning.
- This is a **navigable** workspace graph slice, not yet nested inline directory composite regions, file association edges, or a true system index. The next step is projecting directories as optional collapsed/expanded graph regions without introducing a second data source.

### 3. Normalized resource contract
- `semantic_contract.py` now accepts `origin='resource'` with the same graph/node/port/edge identity checks as source and authored drafts.
- `contains` and `imports` are reserved relation types, but the filesystem provider does **not** invent those edges today. In particular, directory siblings should not be connected by execution/data wires.
- This contract is still a validated snapshot rather than the sole renderer-facing interface; migrate Qt consumption incrementally and keep the current tests as evidence.

## Evidence and limits
- Existing 164 unit tests retained, plus 9 filesystem tests, passing headlessly.
- Python source compile, run-the-examples and archive checks are part of `doctor.sh` and release qualification.
- Qt smoke now includes browsing a temporary directory, opening a nested directory and Python file, return/callable visibility checks, and resource descriptor verification.
- **Native Qt smoke requires Linux/Windows with PyQt6.** It has not been run in the package build environment.

## High-priority follow-ups
1. Move module `if` children into actual source-backed call nodes with correct scope/identity and cross-file associations. Do not treat a definition reference as an executed call.
2. Remove remaining inner/outer port visualization special cases by making one canonical boundary-anchor resolver used for all resource/program graphs. Test geometry at multiple zoom levels on real Qt.
3. Migrate Qt toward consuming normalized descriptors for all graph kinds, and gradually separate application shell/renderer/interaction modules. Never create a parallel source of truth.
4. Resource associations: provenance-backed Python `import` relationships, on-demand visibility, lazy nested folder regions and safe refresh/conflict handling.
