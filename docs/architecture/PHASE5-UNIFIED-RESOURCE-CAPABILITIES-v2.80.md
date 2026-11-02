# v2.80 Architecture Review — Unified Workspace Graph: Resource Capabilities

**Status:** bounded implementation; native Qt qualification pending. **Host baseline:** v2.79 (930 tests; four native Qt stages passed, `qualification-20261101-215444-26885.tar.gz`).

## Accepted product direction

Studio is one extensible workbench, not separate filesystem and programming products. A directory, source file, binary asset, function, and graph-owned program can all appear as graph-view resources and can open independent tab-local *views*. Resources retain one identity across views. A view has its own camera/selection/history, never an independent editable copy of the underlying document. Python is the initial qualified language; the model is explicitly intended to support further language adapters, text editors, previews, commands, tasks, debugging, and extensions. Universal **presentation** does not imply universal execution semantics or a shared writable AST.

The resource graph is a bounded *read-only projection*. The existing `ResourceEntry`, `directory_graph`, `GraphDescriptor`, `GraphCanvas`, navigation routes, `SourceDocumentSession`, and `PythonDocument` retain authority. `ProgramGraph` stays the owner of graph-authored executable documents. No universal document, writable resource registry, compiler, or extension host has been added.

## Alternative architectures evaluated

1. **Replace all source, resource, and program documents with one universal mutable graph.** Rejected. This violates existing source ownership, source fidelity, graph schemas, and type/control semantics; makes every binary and language adapter a special case of a single compiler; and causes destructive synchronization risk.
2. **One workbench, shared presentation/navigation, and capability-based resource projections on existing authorities.** Adopted. Incrementally consolidate mode dispatch as existing native UI behavior is characterized. Add only backed-by-evidence relationships and providers justified by concrete file types.

## Implemented bounded v2.80 slice

- The existing resource adapter advertises `preview_kind` for eligible regular files; no speculative universal file decoder. `.py` can expand to a **saved-source, read-only symbol summary** from the existing `PythonDocument` parser. This is not yet an inline editable Python execution graph. Previews are bounded (12 definitions, existing Python analysis cap).
- A PNG/JPEG/GIF/BMP/WebP node can expand inside the **same resource canvas**. Qt decodes on demand using `QImageReader` with dimension, file-size and scaled-pixel limits; binary pixels are never serialized to graph documents or semantic descriptors. Symlinks, oversize files and invalid data cannot force traversal or file writes. Thumbnails are bounded presentation cache entries, not another asset store.
- The existing opt-in resource relationship overlay now includes source-literal references from Python `open('filename')`, `Path('filename')`, and `Image.open('filename')`. Only direct sibling files *already in the visible listing* are candidates. Edges are `reference`, not execution; certainty is `literal-path-candidate`, with exact source-line evidence. Dynamic paths, paths outside the visible directory, symlinks and arbitrary strings are not inferred as dependencies. The original local `imports` overlay remains intact.
- The same expand control handles folders and qualified file previews. Ctrl+double-click retains Python new-tab navigation, while normal double-click expands a file node. No new `GraphCanvas` subclass, file document authority, or parallel tab manager was introduced.
- Added seven headless regressions and a native Qt smoke stage, including source-backed reference edges, security bounds, graph contracts, stable resource IDs, and previews. Headless qualification is necessary but does not qualify Qt rendering on Linux.

## Intentional limitations / next work

1. **Inline source graph:** Replace the Python symbol summary with the existing qualified Python projection embedded as a nested, read-only graph inside the resource card, with shared source-document revision and source identity. Do not copy or mutate AST nodes. Source-owned unsaved buffers must take precedence over saved snapshots when attached.
2. **Universal routing:** Consolidate resource/source/program tab dispatch and shared gestures into one view/session policy after documenting camera, expansion, pending-edits, and history behavior. Retain separate semantic document providers. Do not create an alternate tab registry.
3. **Relationship indexing:** The present opt-in snapshot only analyzes top-level visible siblings; a larger project needs bounded incremental indexing and opt-in relationship layers. Dynamic path resolution remains candidate-only. No whole-repository eager graph or false runtime dependency claims.
4. **Additional previews and text editing:** Extend explicitly by backed capabilities (Markdown, JSON, HTML, PDFs, audio, etc.). A display preview is not a claim to support editing, and a resource extension is not a runtime language definition. Reuse the source-document contract before adding editors.
5. **Architecture cleanup:** Audit resource/source/program dispatch and legacy prototype call sites; characterize before removing. Avoid parallel owners and compatibility shims. Keep tests that prove contracts, consolidate obsolete tests only with verified replacement.
6. **Future extensibility:** Add LSP, DAP and provider/extension contracts only once actual workbench workflows require them; new language semantics remain adapter-owned. No premature extension-host runtime.

## Qualification gates

- Headless: preview is opt-in, stable IDs, safe symlink and size limits, analysis without executing source, exact `GraphDescriptor` edge certainties, no resource or source mutation, no guessed relationships.
- Native: resource view expands image preview, expands .py saved-source symbols, preserves selected path, displays a source-backed reference wire, supports collapse and separate source tab; no modal hang, callback traceback or camera reset.
- Release: integrity manifest, isolated installer, Python-first and publication gates; native host promotion separately.

**Code cleanup:** The resource adapter now shares one capability policy across root entries and nested folder entries. The existing semantic validator accepts a new source-evidence certainty, not a new edge or graph registry. No legacy semantic path was deleted because its call sites still serve distinct persisted data.
