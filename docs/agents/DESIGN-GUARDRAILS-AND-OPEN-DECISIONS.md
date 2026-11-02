# Guardrails, scope gaps and owner decisions still required

This document prevents agents from turning unresolved engineering choices into accidental product defaults. It is not a second ADR registry. The canonical accepted/provisional decisions remain in `docs/architecture/DECISIONS-AND-NON-GOALS.md`.

## Provenance and product

- `v2.52` is the *current uploaded functional baseline*; `v3.1` is the approved **target direction**, not implemented features. Prior v2.50 line numbers/test totals are historical.
- Studio is an extensible IDE (text, visual, resource/file exploration, debug and development tooling), not only a Python node graph editor. Do not let current Python implementation dictate permanent cross-language architecture.
- Python first. A second adapter remains a contract test, not permission for adding a second compiler before Python gates.
- Native incomplete graph documents must save losslessly; they may be non-compilable. Structural validity, semantic validity, generated candidate, last-good published output and explicit execution are separate states.
- No implicit source rewrite on graph save, no executing source on open, no silently eliding reachable incorrect logic.

## Explicitly unresolved (do not make a default without evidence)

1. Full `ProgramGraph` serialization schema, migrations and stable identity strategy.
2. Compiler/lowering intermediate representation and whole-function dependency closure algorithm.
3. Opaque source island UX and source-to-graph reconcile policies for unsupported edits.
4. On-disk recovery journal location, atomic publish across Linux and Windows, and retention.
5. Native Qt UI behavior on target Linux desktop (must run host smoke).
6. Data model for future language debug/symbol/diagnostic protocols and source mappings.
7. Public repo licensing, contribution/release policy, versioning and artifact signing—**none chosen by this handoff**. Do not invent a license or publish a release.
8. Security trust and sandbox permissions for running untrusted user projects, Python tools, external terminals, plugins and future AI assistants. Default: no implicit execution.
9. Performance budgets for very large files or graphs; benchmark before adding caching/indexing subsystems.
10. Third-party tool evaluation (Graphify/Ponytail) and MCP permission governance, measured before installation.

## Release and failure policy

- Every engineering change produces exact test commands/results, changed contracts, reversibility and scope exclusions.
- CI headless is only one gate; Qt host test is mandatory for UI-relevant changes.
- Do not auto-commit/push, replace user working tree, delete previous zip/branch, or update external Git remotes as part of a code agent task without authorization.
- Preserve safe output from failed generation and both sides of a synchronization conflict.
- Add new instructions only after recurring observed mistakes; do not accumulate overlapping mega-prompts.
