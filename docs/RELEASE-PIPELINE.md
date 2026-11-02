# Development, verification and release pipeline

Studio already has one authoritative set of source, install and qualification scripts. This document describes their roles; do not introduce parallel shell install pipelines.

## Development changes

1. Work from a versioned source snapshot. Keep architectural decisions and the canonical queue in `docs/architecture` and `docs/agents/NEXT-TASKS.md`.
2. Implement a cohesive change in its existing owning module, with characterization tests before deleting compatibility paths.
3. Run `bash scripts/agent-verify.sh --headless` for agent-setup checks, Python doctor and headless regressions.
4. If user interactions, rendering, packaging or installation are affected, run `bash scripts/agent-verify.sh --native` on a native-Qt-capable Linux host. The Qt harness exercises real widgets and produces screenshots.
5. Treat timeout, missing Qt, uncaught callbacks and skipped stages as **unqualified**, never as a pass. Preserve the full qualification report for review.

## GitHub CI (as implemented)

`.github/workflows/headless.yml` checks push and pull requests on Linux with a Python 3.12 headless lane and an Ubuntu PyQt6 native-Qt offscreen lane. CI verifies its environment only. A successful CI run does not assert that a particular user's machine or an install/promotion was qualified.

## Candidate archive and local install

- `python3 scripts/build_release.py --output <new-versioned-path>.zip --qualify-headless` writes a deterministic source ZIP with hashes and verifies its manifest. It refuses to overwrite an existing release.
- `install_linux.py` validates the expected versioned archive and supervises qualification before replacing a managed install. The installed version must not be promoted on failure.
- `RUN-ALL.sh` captures doctor and native Qt logs, a machine-readable verdict, and an uploadable compressed report. Only `--launch` explicitly launches after both gates pass.
- Distribution to users should be a **single ZIP plus an inline Bash command**, not a separately downloaded installer script. Source-control setup and installation remain separate tasks.

## Public release policy (proposed, not automated)

- **Pre-alpha** until Python source/graph trust and native UI reliability meet published acceptance gates.
- Release candidates require passing CI and an independently reviewed native host qualification; Windows/macOS need their own evidence before making support claims.
- Public release assets should include the tested archive, checksums, version, limitations, and installation/rollback instructions. No automatic promotion from a green headless run.
- Any actual screenshot in the README should come from a reviewed and qualified Qt run, free of sensitive project content.

The current active technical acceptance criteria remain in `docs/agents/NEXT-TASKS.md`; this pipeline document is the public description, not a second acceptance database.
