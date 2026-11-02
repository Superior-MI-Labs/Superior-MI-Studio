# Local Linux Codex setup and optional integrations

## Repository

If these files were extracted into an existing Git checkout, copy the new guidance/docs/scripts into that repo **without replacing its `.git` or working changes**. If this is a new checkout extracted from ZIP:

```bash
cd Superior-MI-Python-Visual-Programming-Lab-v2.52
git init
git add -A
git commit -m 'Baseline v2.52 with Codex architecture handoff'
bash scripts/agent-verify.sh --headless
codex
```

The package does **not** initialize Git, set a remote, commit, install Codex, or connect account credentials. Configure your Git author identity and Git remote separately. Codex CLI installation/authentication must follow your host's current official instructions.

## Worktree convention

Prefer `git worktree add ../studio-wt-T02 -b agent/T02-document-session` (from your primary tracked checkout) for an independent ticket. A worktree is attached to a single Git repository; don't put one shared `.git/worktrees` folder at a company-wide parent. Rebase/merge via normal review; don't have multiple agents change the same files simultaneously.

## Skill discovery and roles

- `.agents/skills/studio-architecture-review/SKILL.md`: source-first design review and ADR analysis.
- `.agents/skills/studio-safe-refactor/SKILL.md`: small behavior-preserving code extraction/consolidation.
- `.agents/skills/studio-python-roundtrip/SKILL.md`: source ↔ graph correctness and effects.
- `.agents/skills/studio-native-qt/SKILL.md`: host GUI qualification and reproducible failure evidence.
- `.codex/agents/*.toml`: optional read-only specialists; coordinators delegate only when a task benefits.

## Optional Graphify and Ponytail

- Graphify (Graphify-Labs/graphify): a code/document knowledge graph that may speed read-heavy architecture questions. It adds dependencies and an index. **Not installed or auto-enabled** because this small Python codebase already has an AST inventory and `rg`; try only after measuring navigation overhead. Before using its `graphify codex install`, inspect which AGENTS.md changes/hooks it makes and reconcile with our repository policy. Do not let a generated index define program authority.
- Ponytail (DietrichGebert/ponytail; the likely intended name rather than 'poonytail'): agent prompt/effort workflow plugin with lifecycle hooks. **Not installed**: its behavior overlaps with this repo's concise instructions and skills, and hooks require separate trust. Evaluate in an isolated branch after reading its code and documented hooks; it should never bypass our tests, revisions, approvals or safety rules.
- Do not install both by default. A tool that adds another instruction layer must show a measurable benefit, otherwise it increases context load and divergence risk.

Reference documentation (current as of 2026-10-30):
- Codex instructions: https://learn.chatgpt.com/docs/agent-configuration/agents-md
- Codex skills: https://learn.chatgpt.com/docs/customization/overview
- Codex subagents: https://learn.chatgpt.com/docs/agent-configuration/subagents
- Worktrees: https://learn.chatgpt.com/docs/environments/git-worktrees
- Graphify source: https://github.com/Graphify-Labs/graphify
- Ponytail source/install: https://github.com/DietrichGebert/ponytail

## Verification

`bash scripts/agent-verify.sh --headless` runs all existing standard-library tests and the project Python-first qualification. `bash scripts/agent-verify.sh --native` also runs the application's bounded Qt smoke (requires PyQt6 and Linux). `python3 scripts/check_agent_setup.py` checks handoff integrity. Do not use `--launch` as an agent validation task because it starts an interactive UI.
