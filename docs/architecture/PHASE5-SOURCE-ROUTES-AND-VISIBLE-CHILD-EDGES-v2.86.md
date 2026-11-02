# Phase 5 / v2.86 — Root source-tab route policy and visible child-path evidence

**Status:** headless candidate, native Qt pending. v2.81 remains the last independently confirmed Linux host PASS. v2.85 host evidence is not yet available.

## Architecture decision: route ownership

1. **Rejected:** another generalized navigation host, an alternate root-tab `SourceDocumentSession`, or silent source-file reparsing when an already loaded tab switches documents. These create duplicate authorities and repeat the earlier stale-draft/Back-Forward bugs.
2. **Selected:** preserve `GraphViewSessions` and source `SourceDocumentSession`; any *already-loaded* source tab, including the original root `source` anchor, navigates using `_navigate_source_document_in_tab` and the same `_resolve_live_source_route` preflight. History advances only after qualification. A root tab without a loaded source still uses the existing initial file-open path. `_activate_source_view` can bind this uninitialized root without inventing a fake route. The original root resource tab remains a compatibility anchor.

**Tests:** root tab source A→B, Back/Forward, invalid destination refusal preserving cursor, restoration of original route, plus current secondary cross-provider navigation smoke. No document write or source cloning in navigation.

## Architecture decision: resource relationships

1. **Rejected:** walking project trees, following symlinks, accepting `..` parent traversal or evaluating Python expressions to determine real asset paths. Static code alone cannot qualify runtime dependencies.
2. **Selected:** extend existing literal-file candidate provider only when `directory_graph` supplies the current root boundary. Exact path components such as `assets/icon.png` may map to a visible file card in a manually expanded directory. Target must exist in the *already collected bounded snapshot*; source text is the live `SourceDocumentSession` revision when open, not an extra cache. Standalone callers without `workspace_root` continue to support only sibling paths. Relative paths with `..`, backslashes, empty/dot components, absolute paths or symlink segments are refused. The provenance and `literal-path-candidate` certainty are unchanged.

This offers a useful cross-folder system view while preserving the source of truth and bounded I/O. Future work may add declared module resolution under tested package boundaries and per-type relation filters; not in this candidate.

## Release qualification

`bash scripts/agent-verify.sh --headless`: 976 tests and Python-first/ProgramGraph gates PASS. Added native smoke markers `QT_STAGE root-tab-same-provider-route-policy` and `QT_STAGE resource-visible-child-path-evidence`; the previously failing unsaved shutdown stage must also pass. Promote only if all Qt subprocesses complete, then installer can prune obsolete managed releases/logs.
