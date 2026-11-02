# Phase 5 / v2.87 — Canvas render-revision isolation

## Evidence and failure

The uploaded WolfCat-Studio `qualification-20261102-011456-38194.tar.gz` shows `DOCTOR: PASS`, full Qt work through resource relationship and navigation, then `KeyError` from `NodeItem.resize_now` → `GraphCanvas.update_edges` (three uncaught callbacks). The descriptor included a `resource-literal:<source>:<target>` edge that the current global window resource graph did not include. This happens when another tab becomes the selected graph before a queued Qt resize is delivered.

## Options evaluated

1. **Catch `KeyError` or silently drop absent edges. Rejected.** This merely hides the violation and produces intermittently missing relationships, stale port labels and flicker.
2. **Add a second mutable graph registry or force every tab to reparse/rebuild on resize. Rejected.** Duplicates existing providers, increases parser work and risks dirty-source divergence.
3. **Bind each canvas to one validated render revision. Accepted (ADR-035).** Reuse the graph projection already passed to `describe_graph`, without claiming semantic ownership. Node geometry, composite regions, edges and connected-pin indicators use the same canvas descriptor/payload. Rendering only; source/document owners remain unchanged.

## Changes and invariants

- `GraphCanvas.rebuild` selects the current provider once and binds `_render_graph` as a presentation-only reference before creating Qt items. Its raw nodes and edges come exclusively from this projection. This is *not* a second persisted or writable source of truth.
- `validated_edge_payloads` maps edge draw metadata to the ordered immutable `GraphDescriptor`, refusing missing/extra IDs and changed endpoints/relations. A cross-revision repaint now reports a contract violation rather than `KeyError` or silent omission.
- `PortItem._is_connected` reads the owning canvas descriptor for source, resource, draft and ProgramGraph. Cross-tab source aliases cannot repaint a different file's data pin as connected/unconnected.
- A `NodeItem` removed from the scene cannot repaint the canvas via stale timers. Live geometry changes call the existing deferred `request_edge_refresh`, which respects `_rebuilding` and coalesces Qt timers.
- Source edit authority, navigation history, camera/session ownership, code generation, asset resolution and user files are not changed.

## Acceptance

- Headless: eight new adversarial render-revision tests plus existing architecture/compiler gates.
- Native: `QT_STAGE resource-tab-render-revision-isolation` forces delayed + direct edge refresh on an inactive tab with a visible literal-child reference, after switching the active tab to a graph that lacks that edge; the edge must remain. Require all four Qt subprocesses PASS, no uncaught callback exceptions, and safe source-discard teardown.
- Host status: **pending**. v2.81 remains the last proved native PASS. A failed release retains older installations and logs.

## Deferred

Full elimination of all remaining `window.source_graph` reads from editing-specific UI handlers should be assessed with same-provider multi-file gesture scenarios. Do not expand scope by creating a new Qt state framework or writable graph cache. The next major path remains verified relationship layers, unified tab gestures and per-region source reconciliation.

## Host delivery and interactive launch

The reusable release runner invokes the validated installer with `--no-launch`, extracts the host qualification archive, then invokes the *existing* `launch-linux.sh` only after a successful native qualification. This avoids waiting for the interactive editor to close before printing the uploadable report. A qualification failure does not launch or delete the previous verified version.
