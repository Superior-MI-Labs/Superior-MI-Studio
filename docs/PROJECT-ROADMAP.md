# Studio development roadmap

This is a product-direction overview, **not** a parallel engineering task queue. `docs/agents/NEXT-TASKS.md` remains the only active detailed implementation queue. Milestone order depends on tests and architectural readiness, not calendar promises.

## Current phase: trust and consolidation

- The uploaded v2.120 Linux qualification report passes headless and native Qt checks. v2.121 is a new release-portability and compiler-proof cleanup candidate with 1,338 local headless tests passing, but its native Qt and public CI evidence remain pending. This does not publish a stable release.
- Consolidate existing Python compiler-proof implementation, remove redundant passes, improve conflict evidence and keep source immutable until explicit publication.
- Finish graph view, navigation, tab and legacy-root cleanup without splitting document ownership, camera/session identity or source revisions.
- Maintain positive/refusal regression coverage and real Qt interaction checks.

## Next phase: complete Python-first development loop

- More ordinary Python constructs in source-to-graph representations and explicitly proven reconciliation.
- Authoring parity for existing typed graph operations, structured execution, functions, return values and data dependencies.
- Dependency-aware compile/run tasks, diagnostics, linting, testing and debugger integration behind stable toolchain contracts.
- Safe workspace recovery, session persistence, project-wide navigation and resource relationships.

## Platform phase: adapters and extensions

- Language adapters for parsing, diagnostics, code generation and tooling, reusing existing source/graph contracts.
- File/resource capability providers for structured data, media, documents and plugin-owned previews.
- Extension manifests, permission boundaries, extension-host lifecycle and compatibility versions designed before opening third-party execution paths.
- Developer APIs for debugger adapters, compilers, formatters, linters and test runners, without duplicating services per language.

## Product phase: distribution and community

- Reproducible, validated Linux packaging; Windows support only after parity testing; evaluate macOS separately.
- Stable update channels, signed builds if available, release notes and an extension ecosystem.
- Contributor documentation, issue triage, accessibility, performance, large-project tests and maintained examples.

## Non-goals for the current refactor

- Replacing the existing Python compiler with a generic language-agnostic AST importer.
- Shipping a plugin marketplace or bundling external executables before trust and permission contracts are defined.
- Treating every syntax token or file type as an executable graph node.
- Calling the product stable, feature-complete or cross-platform qualified ahead of evidence.
