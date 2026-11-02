# Phase 5 / v2.81 — Embedded Python source graph in the resource workspace

**Status:** headless candidate; native Linux/Qt integration qualification pending. The host-qualified fallback is v2.79.

## Architectural alternatives

1. Embed a second Python editor, parser or Qt graph view inside the resource card. **Rejected:** duplicates the parser, document revision, camera and widget ownership.
2. Reuse `PythonDocument.composite_file_graph()` as the source projection, validate it with `describe_graph(origin='source')`, then namespace an **uneditable** presentation inside `directory_graph()` and the existing `GraphCanvas`. **Chosen.** The projection is not a universal writable AST.

## Bounded implementation

- Only explicitly expanded `.py` resource nodes are parsed. Each projection is capped at 64 source nodes; shared resource canvas remains capped at 180 nodes. Large files may show the module only. No filesystem recursion beyond explicit folder expansion, no Python execution and no source writes.
- A resource card retains its `resource:<path-hash>` identity. Python source node, port, edge and region identities are prefixed by that resource identity, preventing identical identifiers in separate files from colliding. Nested function regions use the same renderer and camera contract as folders. A double-click opens the existing source editor, never a second owner.
- `GraphDescriptor(origin='source')` is validated before projection. Resource graphs cannot pretend to own source spans, return facets, source semantic roles or verified execution effects. Those remain available in the authoritative source view. The resource projection displays source-owned connectivity as read-only presentation.
- `SourceDocumentSession` is consulted first when already open. Its parsed current revision wins over saved bytes; incomplete/invalid revisions display a diagnostic preview, not a last-good stale graph. Active resource views reproject after source qualification. Expanded inactive tabs reproject on activation.
- PNG/image preview and evidence-backed resource reference edges from v2.80 remain untouched.

## Qualified / still pending

Headless tests cover real source connectivity, read-only proof, multiple-file namespace isolation, invalid drafts, nested folders, preservation of on-disk files and route contracts. The extended native smoke checks actual Qt child surfaces and source draft changes, but it has **not run on the user's Linux host**. Further consolidation should target tab navigation behavior and source-region focus without introducing additional state stores.

## Safety / rollback

The installer validates the release ZIP and retains previous installed versions and logs until native qualification succeeds. Native failure does not remove v2.79. Existing source documents are never rewritten by resource expansion or projection.
