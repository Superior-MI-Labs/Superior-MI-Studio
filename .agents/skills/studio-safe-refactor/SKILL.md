---
name: studio-safe-refactor
description: Consolidate or clean up existing Studio Python/Qt code while preserving behavior and preventing new parallel code paths. Use for refactors, duplicate-state removal, dependency boundary repairs and technical debt work.
---

# Safe refactor: preserve before you improve

1. Confirm actual current code/branch and tests; scope a single owner and one measurable reduction of complexity.
2. Trace callers and state mutation, especially `gui.py`, source writer, semantic view and source adapter. Find characterization tests; write missing ones before moving code.
3. Compare in-place correction with new module extraction. Prefer in-place when no independent responsibility exists. New module must own something exclusive and have no circular dependency.
4. Change in small logical steps. Do not leave a shadow adapter, wrapper chain, duplicated registry, obsolete code path or special-case shim. Explicitly remove replaced logic **after** equivalence tests pass.
5. Preserve externally observable behavior: graph rendering, source text/encoding/CRLF, authoring qualification, Qt stage output, undo, saved file formats and installation scripts.
6. Run `bash scripts/agent-verify.sh --headless` plus focused tests. If GUI or interaction changed, require `bash scripts/agent-verify.sh --native` on PyQt6 host. Analyze any Qt hang as failing state, not a skip.
7. Review `git diff --check`, changed line count and code ownership. Record tests, removed vs added paths, risk and rollback. Do not announce PASS for unrun tests.

Stop and escalate if consolidation forces a new source of truth or violates an accepted ADR. Use `studio-architecture-review` to propose the boundary instead.
