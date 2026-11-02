# Contributing to Superior MI Studio

Thanks for considering support. Studio is pre-alpha and in the middle of a deliberate refactor; maintainability matters more than feature count.

## Where help is useful

- Reproduce and isolate a bug with exact version, OS, Python/Qt details and minimal steps.
- Improve regression coverage and native Qt verification, especially navigation, draft preservation and compiler refusals.
- Review the document ownership and Python source/graph equivalence contracts.
- Help with packaging, Linux/Windows testing, accessibility, UI polish, tutorials, screenshots and documentation.
- Review proposed extension/language adapters **as contracts first**, not as a parallel system.

## Engineering workflow

1. Read `AGENTS.md`, `CODEX-START-HERE.md`, `docs/agents/NEXT-TASKS.md` and the relevant architecture decision.
2. Look for the existing owner or pipeline before adding a new module or state store. Compare a minimal extension of the current contract with any proposed new abstraction.
3. Keep each change cohesive. Add positive and adversarial tests. Unsupported source and unknown resource types must fail closed or remain safely opaque.
4. Verify with `bash scripts/agent-verify.sh --headless`; changes to Qt interaction or release behavior also require `bash scripts/agent-verify.sh --native` on a compatible host.
5. Report test commands, results, relevant screenshots, residual risks and any failure diagnostics in the PR. Do not treat a skipped Qt suite as native success.

A pull request should explain the root cause, which authoritative subsystem changed, why there is no second source of truth, and the rollback plan. Do not submit large generated archives, credentials, unreviewed diagnostics or user-specific paths.

**Licensing boundary:** Studio currently has no published software license. Until one is selected, external source-code contributions should be proposed in issues or draft PR discussions; maintainers will not merge externally authored code without an agreed contribution/license policy. Bug reports, analysis and documentation feedback are welcome now.

Be constructive and respectful toward collaborators. For private security findings, use `SECURITY.md` instead of a public issue.
