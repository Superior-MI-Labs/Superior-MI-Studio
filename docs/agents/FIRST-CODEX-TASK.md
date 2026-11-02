# First Codex task: T00 only

Read `AGENTS.md`, `CODEX-START-HERE.md`, `docs/architecture/DECISIONS-AND-NON-GOALS.md`, `docs/agents/REPOSITORY-MAP-v2.52.md`, and current `docs/V252-FUNCTION-CALL-AUTHORING-CONTRACT.md`. Compare the v3.1 target architecture to current v2.52 implementation with concrete file/line and test evidence. Use `studio_mapper` for read-only dependency inventory and `studio_test_reviewer` for independent gate/host-evidence gaps only if parallelism makes this clearer. Do not change production code.

Deliver an updated current-state subsystem inventory, current v2.52 test + GUI qualification status, ranked ownership/refactor opportunities, contradictory assumptions in the older handoff, and a T01 characterization-test plan. Verify with `bash scripts/agent-verify.sh --headless`; mark native Qt as unverified unless actual PyQt6 smoke is run. Do not start Phase 1 implementation without a reviewed decision boundary.
