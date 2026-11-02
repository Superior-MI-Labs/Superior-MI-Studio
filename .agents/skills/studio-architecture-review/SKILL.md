---
name: studio-architecture-review
description: Audit a proposed Superior MI Studio architecture change, trace the existing owner, compare alternatives and prepare an ADR. Use before introducing a subsystem, document owner, graph schema or command pipeline.
---

# Studio architecture review

1. Read `AGENTS.md`, `docs/architecture/DECISIONS-AND-NON-GOALS.md`, `docs/agents/REPOSITORY-MAP-v2.52.md` and the relevant subsystem sections, not every historical review at once.
2. Inspect the current code and callers/tests. Draw a call/dependency and data-ownership map grounded in file/line references. Avoid asserting v2.50 function positions for v2.52.
3. Compare two approaches: **evolve/consolidate the current owner** versus **new component**. Identify invariant risks, migration and long-term debt for each. State whether the feature should be postponed.
4. Identify canonical authority, read/write boundary, source and graph revisions, failure modes and rollback. Check no duplicated buffer, registry, parser, storage, writer, operation catalog or file watcher is proposed.
5. Map tests from `docs/architecture/ACCEPTANCE-MATRIX.csv`; add characterization and adversarial cases before changes.
6. Produce a compact ADR proposal using the template in `docs/architecture/DECISIONS-AND-NON-GOALS.md` and mark unproven components PROVISIONAL. Only edit the accepted decision register if specifically authorized and backed by evidence.
7. If implementation is requested, bound it to a single working vertical slice; hand off to `studio-safe-refactor` for preservation work or `studio-python-roundtrip` for language semantics.

Deliver: observed owner, A/B comparison, decision, changed contracts, failure cases, tests, rollback, scope exclusions.
