# v2.19 — Host Qt recovery, route unification, camera drag

## Actual host failure

WolfCat-Studio's v2.18 `qualification-20261029-033731-221081.tar.gz` reports a `NameError` at `qt_smoke.py` line 817. `resolve_graph` was imported inside `main()`, but `Route` was not imported. `qt_smoke.py` used it only after many other checks; the GUI had already captured screenshots before that test raised. This is a test-harness defect, not evidence that Python graph route resolution failed. The `propagateSizeHints()` messages are nonfatal Qt plugin warnings.

**Fix:** Import `Route` and `resolve_graph` explicitly at module scope; delete the nested `resolve_graph` import. Add a headless AST import preflight so this exact missing global dependency is tested even without PyQt6. Python compilation alone does not catch unresolved names.

## Architecture choices

**Rejected:** duplicate focused/whole-file view updater paths with separate history, position and refresh order. **Selected:** one `_display_source_route` transition, with the existing `resolve_graph` and `GraphDescriptor` as the semantic validation boundary. The two public GUI commands become thin wrappers. Source bytes, AST, return wires, ownership and editing pipeline remain unchanged. The current window still owns the single source canvas, so this is a preparatory consolidation for future independent graph-view sessions, not an assertion that true multiple graph tabs exist.

**Minimap:** The existing `GraphOverview` owns only the drag gesture. One Qt-free `overview_drag_offset` computes the original viewport center offset when the pointer hits the camera rectangle; outside the rectangle, the offset is zero so click-to-center remains intact. It uses the existing canvas camera `centerOn()` and `_save_root_view()`, does not persist another camera and never changes source graph nodes or edges. No additional graph renderer or adapter is introduced.

## Visual review of v2.18 host evidence

The submitted `workspace-navigation.png` shows the minimap partly clipped behind the source-editor dock boundary. Root cause: the overlay was placed in `QGraphicsView.resizeEvent` alone, but Qt may change the *viewport* size when scrollbars or dock layouts change without resizing the view itself. v2.19 now positions/resizes the overlay using the viewport's actual dimensions, in `viewportEvent` when the viewport changes, and tests that its geometry is fully contained after navigation. This is a presentation-only repair, not a new graph or camera authority.

## Validation and limitations

- 343 headless tests pass (337 previous + 6 new test cases).
- Source compile, archive integrity, shell syntax, extracted ZIP doctor, and isolated headless installer rehearsal are release checks.
- **Native Qt is not available in the packaging environment.** The corrected host smoke adds a no-jump viewport drag assertion, maintains canonical graph routing checks, and captures `graph-overview.png`; these remain unqualified until the user's Linux Mint host runs the new ZIP.
- A passed headless test must never authorize previous-version deletion: installer cleanup remains gated on native Qt qualification. A failed Qt test keeps previous versions and logs.
- The existing main-window document/scope/camera ownership still prevents truly independent simultaneous source tabs. Avoid cosmetic QTabWidget duplication; migrate authoritative per-view contexts first.

## Original roadmap (unchanged)

1. Per-view graph context ownership: resource identity, source scope, selection, navigation, camera, and projection state per tab.
2. True independent graph tabs and universal Files-to-source navigation, no separate permanent Python tab once the migration is qualified.
3. Renderer/descriptor consolidation, verified control flow vs uncertain side effects, correct call/return/exception semantics.
4. Qt graph geometry, nested-graph readability and dock ergonomics, using host screenshots and interaction regressions.
5. Read-only second-language adapter, then guarded source-backed visual-edit transformations with round-trip tests.
