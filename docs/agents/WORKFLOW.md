# Engineering workflow for Codex and reviewers

## A. Pick a bounded outcome

State intended behavior, invariants touched, acceptance IDs, files likely owned, and what will **not** be done. For architecture or multi-step work, write a short plan in `docs/agents/plans/` only when the work truly needs persistent cross-turn handoff; do not generate plans for tiny fixes. Keep one agent task per coherent outcome.

## B. Understand before edit

1. Inspect actual Git status and v2.52 code/tests. Don't override another person's uncommitted changes.
2. Trace entry point → owner → downstream contracts → persistence/test path. Try existing `rg`, AST inventory or code search first. Optional Graphify may *supplement* this, not replace source/test inspection.
3. Compare **extend existing owner** versus **new subsystem**; explicitly reject a shimming/duplicate implementation when applicable.
4. Design positive, negative and side-effect/formatting/race cases. Confirm what must remain unchanged.
5. For contentious decisions, present an ADR proposal using `docs/architecture/DECISIONS-AND-NON-GOALS.md`; do not silently alter an accepted invariant.

## C. Modify and verify

- Minimize number of mutable authorities and write paths. Extract responsibilities only at genuine boundary crossings.
- Never change `gui.py` to 'fix' language semantics. Keep document revision, parser, edge eligibility and source transform in owner modules.
- All Python execution requires deliberate user invocation, never document open/preview/import.
- Add characterization tests before risky cleanup, then negative cases (invalid/incomplete source, stale revisions, effectful calls, Unicode/CRLF, external modifications).
- Run focused relevant `unittest` files while editing; run `bash scripts/agent-verify.sh --headless` before release; for UI changes request/collect native Linux `--native` evidence. Treat timeout and callback traceback as failure.
- Review `git diff --check`, full `git diff`, removed vs added logic, obsolete routes and docs drift. If tests cannot run, describe precisely what was not tested.

## D. Parallelism and context discipline

- One coordinator owns scope and integration; built-in `explorer` or project `studio_mapper`, `studio_test_reviewer`, `studio_arch_reviewer` can independently read and return file-specific evidence.
- No elaborate multi-agent chain for a two-line change. Do **not** have two agents edit `gui.py` or authoring contracts concurrently. For independent writers use separate Git worktrees (`git worktree add ../studio-wt-<ticket> -b <branch>`), merge only after tests and code review.
- Keep worktree directories *outside* the repository; no global worktree superdirectory is necessary.
- Keep only compact facts in the coordinator context. On task completion report changed contracts, test commands/results, unresolved concerns and decisions, not raw logs.

## E. Completion / no false greens

An agent's final report: goal + result; existing owner and changes; comparison/why; exact files; exact successful/failed/skipped test commands; source/graph safety review; native GUI evidence if applicable; rollback; next ticket; any ADR revision. Do not self-award 'qualified' because a test exists: show evidence it ran.

## F. Agents and external tools

- Built-in Codex skills under `.agents/skills/` are the default. `AGENTS.md` is the always-read policy file; `SKILL.md` is the *correct* skills filename; `skills.md` at root is not required by Codex.
- Third-party code-intelligence tools are optional. Do not auto-install packages, hooks or network access from a prompt. Verify provenance/license/commands and ensure generated indexes are ignored.
- Local `codex` or IDE session settings should control approvals, sandbox and network trust. Repository config does not grant permission to access sensitive files or external tools.
