# Tool and agent add-on decisions — 2026-10-30

| Tool/system | Decision | Reason and next gate |
|---|---|---|
| Codex repo `AGENTS.md` | Enabled | Short contract automatically loaded; reference detailed docs progressively |
| `.agents/skills/*/SKILL.md` | Enabled | Four domain-specific reusable procedures with front matter |
| `.codex/agents/` | Enabled (optional) | Three **read-only by instruction**, bounded review roles; they share parent permissions, which still require sandbox governance |
| `.codex/config.toml` | Minimal | Only max 3 subagent threads; no forced account model, MCP server, hooks, network or approval override |
| Git worktrees | Recommended for concurrent writers | Avoid cross-file contention; worktree per task, all tied to the **same Git repo** |
| Graphify-Labs/graphify | Deferred experiment | Potential AST/document index; optional after a measured baseline. Installing its Codex rules must not replace our AGENTS.md |
| DietrichGebert/ponytail | Deferred | Additional agent rule/lifecycle hooks may conflict with context economy; no evidence of benefit on Studio yet |
| LSP/MCP/code browser addons | Deferred | Codex can navigate with direct search and source AST; add only if bottleneck measured and security reviewed |
| Automated commits/releases | Disabled | User explicitly authorizes publish; correctness gates remain reviewable |

**Evaluation protocol for add-ons:** (1) inspect license and source, (2) audit files/hooks/commands changed, (3) benchmark on three code-mapping and two refactoring tasks with and without it, (4) track navigation cost, task success, test failures, instruction drift, (5) keep only if useful, remove all generated config and indexes otherwise. No specific claimed speedup percentage is accepted without a controlled Studio measurement.
