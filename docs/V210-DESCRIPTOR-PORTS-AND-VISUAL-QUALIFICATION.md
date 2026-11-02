# v2.10 Engineering decision and verification

## Evidence from actual Linux host

User-supplied `qualification-20261029-000410-214026.tar.gz` was inspected. `doctor.log` ended with **272 tests OK**, and `qt.log` ended with **NATIVE_QT_SMOKE_PASS**. Three native Qt images were inspected. The root and return screenshots suffered from aggressive viewport cropping, and pin labels covered portions of wires because the smoke itself had enabled `port_label_mode=always` early and never restored the default `contextual` mode. This is not evidence of a semantic defect. Return data/control endpoints visibly attach; previous geometry assertions also passed on that host.

## Alternative approaches considered

- **A: migrate all renderer and mutable draft edits in one change.** Rejected for now: the draft inspector directly updates `draft_ports` and calls `item.rebuild()` without refreshing `GraphCanvas.graph_contract`. Enforcing an immutable snapshot on draft edit paths would cause false contract errors, or require broad rewrite of editing lifecycle before host evidence.
- **B: migrate immutable source/resource port iteration first, using the existing validated `NodeDescriptor`, and retain the draft edit authority.** Selected: one small, testable vertical slice with no new graph registry. The helper maps raw visual payloads to immutable descriptor IDs/order, rejects changed identities/types/labels, and never mutates the graph.

## Changes

- `semantic_contract.py`: `validated_port_payloads()` looks up each already-declared port by stable identity. No additional node, port or graph type is created.
- `gui.py`: `NodeItem._ports_for_view()` applies descriptor order to source/resource pin creation, terminal facets, and compact pin labels. Drafts remain mutable via the original inspector path.
- `qt_smoke.py`: restored contextual pin labels after the `always`-mode fixture; captured and fit nested and return cards rather than grabbing an arbitrary root viewport; added early-return capture. Each capture restores the original root view and checks that the card fits the viewport.
- `RUN-ALL.sh`: retains a fourth screenshot in the same report archive.
- `test_v210_descriptor_ports.py`: eight explicit contract tests, including hypothetical future adapter ordering and mismatches.

## Verification and limits

- Build environment: `./doctor.sh` => **280 tests OK**; source compilation and Python graph consistency probes pass.
- The prior v2.9 host result does not qualify v2.10. **This container has no PyQt6**, so the updated Qt capture assertions have not run here. Upload the resulting `qualification-*.tar.gz` from Linux Mint to qualify the new behavior.
- This is a study/presentation prototype. It does **not** compile or execute arbitrary graph programs. `.py` text stays authoritative; source edits continue through existing guarded review.

## Forward plan

1. Host verify screenshots and fix only demonstrated geometry issues.
2. Consolidate descriptor-driven port editing and avoid stale draft snapshots through one mutation transaction.
3. Normalize semantics for invocation, effects and exceptional exits, keeping a clear boundary between proven execution and uncertainty.
4. Demonstrate a small read-only second language adapter without any second renderer; require cross-language contract, provenance and source-identity tests.
