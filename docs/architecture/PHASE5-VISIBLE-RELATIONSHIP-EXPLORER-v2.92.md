# Phase 5: Bounded visible relationship exploration (v2.92)

## Two options considered

1. A recursive project-wide dependency index and independent search state. **Rejected:** it would scan extra paths, duplicate source freshness rules and imply runtime authority the static Python candidate adapters do not have.
2. A deterministic query over each resource canvas's existing validated `GraphDescriptor`. **Selected:** bounded, reuses the one resource graph and source owners, and makes already-visible file evidence discoverable.

## Contracts

- `search_resource_relationships` accepts a validated resource graph descriptor and exact producer payload. The normal semantic edge validator runs once per query. Every returned candidate additionally passes endpoint identity, path-within-root and no-symlink / regular-file checks. Search never reads files, examines hidden or unexpanded directories or mutates source.
- Searches match the source and target names, relation, certainty, and already-captured evidence syntax. Max query length 128; deterministic ordering; at most 48 returned results (24 in the UI). Count and kind summaries account for all visible matching edges; a result cap cannot falsify totals.
- The Qt Inspector uses the selected canvas's existing descriptor and render payload; no registry or cache. A typed query updates only a bounded list of buttons. Result buttons capture the specific canvas, descriptor and payload revisions and refuse stale selection. Inspecting a candidate delegates to existing `show_resource_relationship` and its evidence/source/target actions.
- A file-card context action opens the explorer for that file without hiding other cards. Toolbar action opens all visible candidates. Per-tab overlay, focus and direction filters remain the graph producer's authority. Empty overlays show zero candidates and do not initiate any discovery.

## Verification and limits

- Headless regression: query identity, source evidence, type counts, stable bounded results, focused neighborhood, active drafts, missing/symlink endpoints, unsupported descriptor, stale raw edges, no filesystem mutation.
- Native Qt: query widget and result actions, search counts and Inspector transition, selected-tab and rendered-revision refusal, no uncaught callbacks, alongside earlier inactive-canvas and shutdown tests.
- This is static relationship evidence, **not** a proven runtime dependency graph, a background search index or an editor. v2.88 is still last confirmed native baseline until a later report demonstrates full Qt success.
