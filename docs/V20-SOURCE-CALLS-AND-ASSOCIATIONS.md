# v2.0 — Source-backed call sites, local import candidates, and contract-driven rendering

**Release scope:** standalone native PyQt6 research app, continuing v1.9. It has not been merged into the official Superior MI Studio repo. Readable graphs remain derived from Python source, not an independent executable language.

## 1. Source calls, not an opaque call summary

- `PythonDocument._module_graph()` now identifies `ast.Call` **at module execution level**: direct expressions, calls inside top-level control statements (e.g., `if __name__ == '__main__'`), and calls as RHS initializers of module bindings.
- Each call receives its own AST source span, stable ID derived from its source span, and typed callable-in/result-out ports. Nested **positional call** expressions receive a real child result -> parent argument edge. A module binding initialized by a direct call receives a real call-result -> binding edge.
- A top-level `IF` with supported call expressions uses the **same** recursive child surface already used by functions and loop bodies. The `IF` statement is the region owner. It does not create new fake execution operations. Source calls in the true and false arms currently share one region; their separate branch semantics are not yet lowered. This must not be mistaken for an execution trace.
- Existing `MODULE IF` analysis ports and reference edges are retained for backward compatibility but hidden in readable view; definition-to-call links are tagged `syntactic-name-match`, not guaranteed runtime dispatch (a name may be rebound). There is no implicit imported-module execution when opening a file.
- A function body isn't traversed for module-level call sites; calls inside function bodies remain owned by their function graph, not treated as module-init execution.

## 2. Files/System resource association overlay

- The resource graph is **still read-only** and lists only immediate directory entries. The toolbar has a checkable `Import links` overlay, off by default.
- It statically parses only visible **regular** `.py` files, at most 512 KiB each, and only recognizes candidate imports of adjacent `.py` files. For `from . import helper`, the directory must contain a regular `__init__.py`.
- Imported names are **syntactic local-file candidates**, not proof of Python runtime import resolution. The graph refuses to invent links for unknown packages, `sys.path`, dotted modules, dynamic `__import__`, or invisible resources. Symlink file candidates aren't followed.
- The overlay adds ordinary `imports` edges and source-line provenance. Hovering a line shows the path, line, syntax, and certainty. The overlay does not create files, import or execute Python, follow child directories, or modify a source file.
- A single edge aggregates multiple import statements for the same visible pair; target/source path identities remain the same with the overlay off and on.

## 3. One canonical structural interface

- `semantic_contract.py` continues as the **read-only, versioned contract** shared by source, draft, and resource graphs. No second node or edge registry is created.
- Edge descriptors now include optional immutable `SourceEvidence` and `certainty`. Call-reference and import-candidate edges retain source provenance through validation.
- The Qt canvas now uses validated descriptor identity/order to decide **which nodes and edges exist**. Legacy graph dicts still provide geometry, pin UI, and styling. This is an incremental migration, not a claim that renderer migration is complete.
- Source transforms still go through the existing guarded Python edit pipeline; graph browsing and association changes are presentation-only.

## 4. Qualification and follow-ups

The package runs the pre-existing **173 tests** plus **10 new tests** (183 total) covering source call sites, calls inside top-level IF, same-line nested calls, direct-call module initializers, no accidental function-body execution, import candidate evidence, symlink safety, pagination, syntax-error tolerance, and never executing code during static inspection.

The Qt smoke test now includes source-call selection/highlighting, recursive ownership, toggling candidate imports, validated resource edges, and edge tooltips. The smoke test requires PyQt6 and **has not been executed in the build environment**. Follow the host runbook in README.

**Not yet qualified or implemented:** runtime-precise call-target resolution, cross-package and cross-directory associations, dynamic imports, first-class scope/branch semantics for module IF call sites, inline nested directory graphs, multi-language parsers, graph-to-source editing of the new call-site edges, and complete presentation data migration out of legacy dictionaries.

Next work: resolve call references with explicit uncertainty and cross-file provenance; make `resource_graph` expandable inline through existing GraphSurface; separate renderer/navigation/application Qt classes without creating duplicate APIs.
