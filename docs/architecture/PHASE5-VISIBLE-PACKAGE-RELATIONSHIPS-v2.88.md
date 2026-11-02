# Phase 5 / v2.88 — Visible package associations and presentation layers

## Architecture and options

The workspace currently links visible sibling Python imports and literal asset-path candidates. Explicitly expanded folders expose file nodes, but Python package imports across those folders have lacked evidence wires.

1. **Reject:** a project-wide import resolver, recursive file scanner or new dependency database. Actual Python imports depend on sys.path, import hooks, namespace packages, virtual environments and conditional execution; the resolver would imply unsupported runtime certainty and acquire a second source/index authority.
2. **Accept (ADR-036):** extend `source_associations` and the existing `directory_graph` with opt-in visible package names and explicitly selected relationship layers. Only file cards already present in the bounded snapshot are eligible; no additional directories are opened.

## Contract

- An absolute dotted module such as `pkg.render` is anchored to the browsed workspace root only when `workspace_root` is supplied. An unqualified `util` stays adjacent to its source, preserving standalone behavior.
- All intermediate package directories must expose a regular, non-symlink `__init__.py` node. Fully visible `pkg/__init__.py` may itself be the import candidate for `import pkg`. No namespace-package or sys.path guess, no more than four module name components.
- `from .render import name` is considered only with an existing one-level package initializer. `from ..` is refused. Declaration matching is a name/line heuristic, never proof of runtime binding.
- Source bytes are read through nonblocking, nofollow descriptors, `fstat`-validated as regular files and bounded at 512,000 bytes. Python encoding cookies are detected with the standard tokenizer. Open `SourceDocumentSession` text always wins over saved bytes, including invalid drafts which produce no edges.
- In resource navigation menu, `Show file relationships` globally controls the overlay, while `Import candidates` and `Literal file references` select separate presentation layers for the current tab. These are read-only switches and do not create alternative graph stores or modify source. Every graph is validated and per-canvas rendering remains pinned to its own descriptor revision (ADR-035).

## Verification and risks

Headless tests include standalone sibling policy, expanded/hidden/nested packages, relative imports, symbol declarations, symlinked directories, invalid/live/oversized/PEP-263 sources, and typed edge-layer contract parity. Native Qt smoke adds `resource-relationship-layer-and-tab-isolation`, then repeats the delayed inactive-tab render-revision isolation check. The whole Qt suite must pass on Linux before promotion.

**Not implemented:** a full Python module loader, a graph of arbitrary runtime dependencies, transitive closure, fuzzy source imports, namespace packages, or a global project index.
